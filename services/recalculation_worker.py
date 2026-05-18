import logging
import time
from DB.db import db_execute
from services.priority_engine import calculate_aging_bonus

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 60


def recalculate_queue() -> None:
    rows = db_execute(
        """
        SELECT id, created_at, keyword_score, ai_score
        FROM news_queue
        WHERE status = 'pending'
        """,
        fetchall=True,
    )

    if not rows:
        return

    now = time.time()

    for row in rows:
        queue_id     = row["id"]
        created_at   = float(row["created_at"])
        keyword_score = row["keyword_score"] or 0.0
        ai_score      = row["ai_score"]      or 0.0

        aging_score = calculate_aging_bonus(created_at, now)
        final_score = keyword_score + aging_score + ai_score

        db_execute(
            """
            UPDATE news_queue
            SET aging_score  = %s,
                final_score  = %s,
                last_updated = NOW()
            WHERE id = %s
            """,
            (aging_score, final_score, queue_id),
        )

    logger.debug(f"🔄 Queue recalculated ({len(rows)} pending items)")


def recalculation_worker() -> None:
    logger.info("🚀 Recalculation worker started")

    while True:
        try:
            recalculate_queue()
        except Exception as exc:
            logger.error(f"❌ Recalc error: {exc}", exc_info=True)

        time.sleep(_INTERVAL_SECONDS)
