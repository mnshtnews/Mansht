import logging
from typing import Optional

from DB.db import db_execute
from services.priority_engine import calculate_final_score

logger = logging.getLogger(__name__)


class QueueManager:

    def add_or_update_queue_item(self, article: dict) -> None:

        scores = calculate_final_score(
            article["title"],
            article.get("content") or "",
            article["created_at"],
        )

        db_execute(
            """
            INSERT INTO news_queue (
                article_id,
                title,
                url,
                content,
                image_url,
                created_at,
                keyword_score,
                aging_score,
                ai_score,
                final_score,
                status,
                last_updated
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
            ON CONFLICT (url) DO UPDATE SET
                keyword_score = EXCLUDED.keyword_score,
                aging_score   = EXCLUDED.aging_score,
                ai_score      = EXCLUDED.ai_score,
                final_score   = EXCLUDED.final_score,
                image_url     = EXCLUDED.image_url,
                last_updated  = NOW()
            """,
            (
                article["article_id"],
                article["title"],
                article["url"],
                article.get("content"),
                article.get("image_url"),
                article["created_at"],
                scores["keyword_score"],
                scores["aging_score"],
                scores["ai_score"],      
                scores["final_score"],
            ),
        )

        logger.debug(
            f"Queued article_id={article['article_id']} "
            f"score={scores['final_score']:.2f}"
        )

    def reorder_queue(self) -> None:
        
        db_execute(
            """
            UPDATE news_queue
            SET final_score = keyword_score + aging_score + ai_score
            WHERE status = 'pending'
            """
        )

    def get_next_post(self) -> Optional[dict]:
        
        import psycopg2
        import os
        from psycopg2.extras import RealDictCursor
        from config.settings import MAX_QUEUE_AGE_HOURS

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        try:
            conn.autocommit = False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM news_queue
                    WHERE status = 'pending'
                    ORDER BY
                        -- Overdue articles first (age > MAX_QUEUE_AGE_HOURS)
                        CASE WHEN (EXTRACT(EPOCH FROM NOW()) - created_at) / 3600
                                  > %(max_age)s
                             THEN 0 ELSE 1
                        END ASC,
                        -- Among overdue: oldest first
                        created_at ASC,
                        -- Among normal: highest score first
                        final_score DESC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """,
                    {"max_age": MAX_QUEUE_AGE_HOURS},
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None

                cur.execute(
                    """
                    UPDATE news_queue
                    SET status = 'processing', last_updated = NOW()
                    WHERE id = %s
                    """,
                    (row["id"],),
                )
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
