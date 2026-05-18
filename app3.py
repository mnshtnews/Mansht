import os
import random
import time
from functools import partial
from threading import Thread
import requests
from dotenv import load_dotenv
from supabase import create_client
from config.settings import SCRAPE_INTERVAL_MIN, SCRAPE_INTERVAL_MAX
from DB.cloud_storage import upload_image
from image.composer import generate_post_image
from scraper.extractor import get_html, extract_news
from scraper.publisher import send_photo
from scraper.save_news import save_news
from services.scheduler import publishing_worker
from services.recalculation_worker import recalculation_worker
from utils.logger import logger


load_dotenv()

TOKEN        = os.getenv("TOKEN")
CHAT_ID      = os.getenv("CHAT_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([TOKEN, CHAT_ID, SUPABASE_URL, SUPABASE_KEY]):
    raise RuntimeError(
        "Missing required environment variables: "
        "TOKEN, CHAT_ID, SUPABASE_URL, SUPABASE_KEY"
    )

supabase = create_client(str(SUPABASE_URL), str(SUPABASE_KEY))


BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

TEMPLATE_CONFIG = {

    "رياضة": {
        "template":  os.path.join(TEMPLATES_DIR, "رياضة.png"),
        "image_box": (0, 0, 1080, 835),
        "text_box":  (0, 940, 1060, 1200),
        "align":     "center",
    },

    "سياسة": {
        "template":  os.path.join(TEMPLATES_DIR, "سياسة.png"),
        "image_box": (0, 0, 1080, 820),
        "text_box":  (340, 820, 1070, 1050),
        "align":     "center",
    },

    "فن": {
        "template":  os.path.join(TEMPLATES_DIR, "عام.png"),
        "image_box": (46, 188, 1040, 744),
        "text_box":  (10, 845, 1070, 1210),
        "align":     "center",
    },

    "اجتماعية": {
        "template":  os.path.join(TEMPLATES_DIR, "اجتماعية.png"),
        "image_box": (46, 188, 1040, 744),
        "text_box":  (10, 845, 1070, 1210),
        "align":     "center",
    },

    "عام": {
        "template":  os.path.join(TEMPLATES_DIR, "عام.png"),
        "image_box": (46, 188, 1040, 744),
        "text_box":  (10, 845, 1070, 1210),
        "align":     "center",
    },

}


from scraper.extractor import session as _scraper_session


def _generate_image(
    title, image_url, news_id, url,
    category, confidence, content,
    send_to_telegram=False,
):
    """Wrapper that injects all runtime deps into image/composer.py."""
    return generate_post_image(
        title=title,
        image_url=image_url,
        news_id=news_id,
        url=url,
        category=category,
        confidence=confidence,
        content=content,
        template_config=TEMPLATE_CONFIG,
        session=_scraper_session,
        upload_fn=upload_image,
        supabase_storage=supabase.storage,
        send_telegram_fn=send_photo,
        send_to_telegram=send_to_telegram,
    )



def run() -> None:
    first_run = True

    while True:
        try:
            logger.info(f"\n🔄 Checking for news... ({time.strftime('%H:%M:%S')})")

            html  = get_html()
            limit = 5 if first_run else 50
            news  = extract_news(html, limit=limit)
            first_run = False

            if news:
                save_news(news, TEMPLATE_CONFIG, _generate_image)
                logger.info(f"✅ Added {len(news)} articles.")
            else:
                logger.info("😴 No new updates.")

            time.sleep(random.randint(SCRAPE_INTERVAL_MIN, SCRAPE_INTERVAL_MAX))

        except requests.exceptions.RequestException as exc:
            logger.error(f"🌐 Network error: {exc}")
            time.sleep(10)
            continue     

        except Exception as exc:
            logger.error(f"⚠️ Loop error: {exc}")
            time.sleep(5)



if __name__ == "__main__":
    try:
        Thread(target=publishing_worker, daemon=True).start()
        Thread(target=recalculation_worker, daemon=True).start()
        logger.info("🚀 Workers started")
        run()
    except KeyboardInterrupt:
        logger.info("🛑 Stopped manually")
    except Exception as exc:
        logger.error(f"CRASH: {exc}")
        raise
