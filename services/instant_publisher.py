
import logging
import unicodedata
from typing import Optional
from config.settings import INSTANT_PUBLISH_KEYWORDS, ENABLE_FACEBOOK_POSTING
from DB.db import db_execute

logger = logging.getLogger(__name__)



def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _build_search_text(title: str, content: Optional[str]) -> str:
    parts = [_normalise(title)]
    if content:
        parts.append(_normalise(content))
    return " ".join(parts)



def is_priority_article(title: str, content: Optional[str] = None) -> bool:
    
    normalised_title = _normalise(title)

    for keyword in INSTANT_PUBLISH_KEYWORDS:
        normalised_keyword = _normalise(keyword)
        if normalised_keyword in normalised_title:
            logger.info(
                f"🚨 PRIORITY MATCH | keyword='{keyword}' | title='{title[:80]}'"
            )
            return True

    return False


def _claim_queue_row(queue_id: int) -> bool:
    
    import psycopg2
    import os

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE news_queue
                SET status = 'processing', last_updated = NOW()
                WHERE id = %s AND status = 'pending'
                """,
                (queue_id,),
            )
            claimed = cur.rowcount == 1
        conn.commit()
        return claimed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def instant_publish(
    post: dict,
    priority_tg_publisher,
    fb_publisher,
) -> None:
    
    queue_id   = post["id"]
    title_snip = post.get("title", "")[:80]

    
    if not _claim_queue_row(queue_id):
        logger.warning(
            f"🚨 INSTANT PUBLISH SKIPPED — row already claimed | queue_id={queue_id}"
        )
        return

    logger.info(
        f"🚨 INSTANT PUBLISH START | queue_id={queue_id} | '{title_snip}'"
    )

    telegram_status = "pending"
    facebook_status = "pending"

    try:
        priority_tg_publisher.publish(post)
        telegram_status = "sent"
        logger.info(
            f"🚨 INSTANT PUBLISH ✅ Telegram sent | queue_id={queue_id}"
        )
    except Exception as exc:
        telegram_status = "failed"
        logger.error(
            f"🚨 INSTANT PUBLISH ❌ Telegram error | queue_id={queue_id} | {exc}"
        )

    if ENABLE_FACEBOOK_POSTING:
        try:
            success = fb_publisher.publish(post)
            facebook_status = "sent" if success else "failed"
            logger.info(
                f"🚨 INSTANT PUBLISH {'✅' if success else '⚠️'} Facebook "
                f"| queue_id={queue_id}"
            )
        except Exception as exc:
            facebook_status = "failed"
            logger.error(
                f"🚨 INSTANT PUBLISH ❌ Facebook error | queue_id={queue_id} | {exc}"
            )

    db_execute(
        """
        UPDATE news_queue
        SET
            status          = 'published',
            telegram_status = %s,
            facebook_status = %s,
            published_at    = NOW(),
            last_updated    = NOW()
        WHERE id = %s
          AND status = 'processing'
        """,
        (telegram_status, facebook_status, queue_id),
    )

    logger.info(
        f"🚨 INSTANT PUBLISH COMPLETE | queue_id={queue_id} "
        f"| tg={telegram_status} fb={facebook_status}"
    )
