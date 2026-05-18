import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TOKEN   = os.getenv("PRIORITY_TELEGRAM_BOT_TOKEN")
_CHAT_ID = os.getenv("PRIORITY_TELEGRAM_CHAT_ID")

_CAPTION_LIMIT = 1024


class PriorityTelegramPublisher:

    def __init__(self):
        if not _TOKEN or not _CHAT_ID:
            raise RuntimeError(
                "PRIORITY_TELEGRAM_BOT_TOKEN and PRIORITY_TELEGRAM_CHAT_ID "
                "must be set in the environment."
            )

    def _caption(self, post: dict) -> str:
        raw = (
            f"📰 {post['title']}\n\n"
            f"{(post.get('content') or '')[:500]}\n\n"
            f"🔗 {post['url']}"
        )
        return raw[:_CAPTION_LIMIT]

    def publish(self, post: dict) -> bool:
        caption   = self._caption(post)
        image_url = post.get("image_url")

        try:
            if image_url:
                resp = requests.post(
                    f"https://api.telegram.org/bot{_TOKEN}/sendPhoto",
                    data={"chat_id": _CHAT_ID, "photo": image_url, "caption": caption},
                    timeout=30,
                )
            else:
                resp = requests.post(
                    f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
                    data={"chat_id": _CHAT_ID, "text": caption},
                    timeout=30,
                )

            if resp.status_code != 200:
                logger.error(
                    f"❌ Telegram API {resp.status_code}: {resp.text[:200]}"
                )
                return False

            logger.info(f"✅ Priority Telegram sent | {post['title'][:60]}")
            return True

        except Exception as exc:
            logger.error(f"❌ Priority Telegram error: {exc}")
            return False
