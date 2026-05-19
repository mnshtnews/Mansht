import time

from config.settings import ENABLE_FACEBOOK_POSTING
from services.queue_manager import QueueManager
from services.facebook_publisher import FacebookPublisher
from services.priority_telegram_publisher import PriorityTelegramPublisher
from DB.db import db_execute
from utils.logger import logger

_queue       = QueueManager()
_fb          = FacebookPublisher()
_priority_tg = PriorityTelegramPublisher()


def _publish_one(post: dict) -> None:
    import time
    from config.settings import MAX_QUEUE_AGE_HOURS

    post_id         = post["id"]
    telegram_status = "pending"
    facebook_status = "pending"

    age_hours = (time.time() - post.get("created_at", time.time())) / 3600
    if age_hours > MAX_QUEUE_AGE_HOURS:
        logger.warning(
            f"⏰ Publishing OVERDUE article | id={post_id} "
            f"| age={age_hours:.1f}h | {post['title'][:50]}"
        )

    try:
        _priority_tg.publish(post)
        telegram_status = "sent"
        logger.info(f"✅ Telegram sent  | id={post_id} | {post['title'][:60]}")
    except Exception as exc:
        telegram_status = "failed"
        logger.error(f"❌ Telegram error | id={post_id} | {exc}")

    if ENABLE_FACEBOOK_POSTING:
        try:
            success = _fb.publish(post)
            facebook_status = "sent" if success else "failed"
            level = logger.info if success else logger.warning
            level(f"{'✅' if success else '⚠️'} Facebook | id={post_id}")
        except Exception as exc:
            facebook_status = "failed"
            logger.error(f"❌ Facebook error | id={post_id} | {exc}")

    db_execute(
        """
        UPDATE news_queue
        SET
            status           = 'published',
            telegram_status  = %s,
            facebook_status  = %s,
            published_at     = NOW(),
            last_updated     = NOW()
        WHERE id = %s
          AND status = 'processing'
        """,
        (telegram_status, facebook_status, post_id),
    )


def publishing_worker() -> None:

    logger.info("🚀 Publishing worker started (real-time mode)")

    while True:
        try:
            post = _queue.get_next_post()
            if post:
                _publish_one(post)
                continue         
        except Exception as exc:
            logger.error(f"⚠️ Publishing worker error: {exc}", exc_info=True)

        time.sleep(5)
