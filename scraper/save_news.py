import time
import traceback
from datetime import datetime
from DB.db import db_execute
from ML.ai import classify_news
from services.date_filter import is_within_range
from services.instant_publisher import is_priority_article, instant_publish
from services.priority_telegram_publisher import PriorityTelegramPublisher
from services.facebook_publisher import FacebookPublisher
from services.queue_manager import QueueManager
from utils.logger import logger

queue        = QueueManager()
_priority_tg = PriorityTelegramPublisher()
_fb          = FacebookPublisher()


def save_news(
    news: list[dict],
    template_config: dict,
    generate_image_fn,
) -> None:
    
    for item in news:
        try:
            category, confidence = classify_news(
                item["title"],
                content=item.get("content"),
            )

           
            if category is None:
                logger.warning(f"⚠️ Low confidence: {item['title']}")
                category   = "عام"
                confidence = 0.0

            if category not in template_config:
                category = "عام"

            
            already_exists = db_execute(
                "SELECT id FROM news WHERE url = %s OR title = %s LIMIT 1",
                (item["url"], item["title"]),
                fetch=True,
            )
            if already_exists:
                logger.warning(f"⚠️ Article already exists (url or title): {item['title'][:60]}")
                continue

            result = db_execute(
                """
                INSERT INTO news (title, url, image, category, confidence, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
                """,
                (
                    item["title"],
                    item["url"],
                    item["image"],
                    category,
                    confidence,
                    item.get("content"),
                ),
                fetch=True,
            )

            if not result:
                logger.warning(f"⚠️ Article already exists: {item['title']}")
                continue

            news_id = result["id"] if isinstance(result, dict) else result[0]

            if not news_id:
                logger.error("❌ No news_id returned from DB")
                continue

            logger.info(f"\n🟢 New article: {item['title']}")


            image_url = generate_image_fn(
                item["title"],
                item["image"],
                news_id,
                item["url"],
                category,
                confidence,
                item.get("content"),
                send_to_telegram=False,
            )

            if not image_url:
                logger.error(f"❌ Image generation failed for: {item['title']}")
                continue


            article_date = datetime.utcnow()
            if is_within_range(article_date):
                queue.add_or_update_queue_item({
                    "article_id": news_id,
                    "title":      item["title"],
                    "url":        item["url"],
                    "content":    item.get("content"),
                    "image_url":  image_url,
                    "created_at": time.time(),
                })

                
                if is_priority_article(item["title"], item.get("content")):
                    queue_row = db_execute(
                        """
                        SELECT *
                        FROM news_queue
                        WHERE article_id = %s
                          AND status = 'pending'
                        LIMIT 1
                        """,
                        (news_id,),
                        fetch=True,
                    )
                    if queue_row:
                        instant_publish(queue_row, _priority_tg, _fb)
                    else:
                        logger.warning(
                            f"🚨 Priority article has no pending queue row "
                            f"| article_id={news_id} | '{item['title'][:60]}'"
                        )

            db_execute(
                """
                UPDATE news_queue
                SET image_url = %s, generated_image = %s
                WHERE article_id = %s
                """,
                (image_url, f"news_{news_id}.jpg", news_id),
            )

            if confidence >= 0.65 and category != "عام":
                db_execute(
                    """
                    INSERT INTO confirmed_training (title, category, confidence)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (title) DO NOTHING
                    """,
                    (item["title"], category, confidence),
                )

        except Exception as exc:
            logger.error(f"❌ Save error: {exc}")
            traceback.print_exc()
