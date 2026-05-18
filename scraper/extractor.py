import re
import unicodedata
from typing import Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed
from DB.db import db_execute
from utils.logger import logger

BASE_URL = "https://mnsht.net"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

session = requests.Session()
session.headers.update(HEADERS)




def clean_text(text) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def clean_image_url(src: Optional[str]) -> Optional[str]:
    if not src:
        return None
    full_url = urljoin(BASE_URL, src)
    full_url = full_url.replace("/UploadCache/libfiles/", "/Upload/libfiles/")
    full_url = re.sub(r"/\d+x\d+o?/", "/", full_url)
    return full_url




def news_exists(url: str, title: Optional[str] = None) -> bool:
    
    if title:
        result = db_execute(
            "SELECT id FROM news WHERE url = %s OR title = %s LIMIT 1",
            (url, title),
            fetch=True,
        )
    else:
        result = db_execute(
            "SELECT id FROM news WHERE url = %s LIMIT 1",
            (url,),
            fetch=True,
        )
    return bool(result)




@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def get_html() -> str:
    
    response = session.get(BASE_URL, timeout=(10, 30))
    response.raise_for_status()
    return response.text


def fetch_article_content(url: str, max_words: int = 150) -> Optional[str]:
    
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        tag  = soup.select_one("div.paragraph-list")
        if not tag:
            return None

        paragraphs = tag.find_all("p")
        content    = " ".join(p.get_text(strip=True) for p in paragraphs)
        words      = content.split()

        chunk       = " ".join(words[:max_words])
        cutoff      = " ".join(words[:30])
        search_area = chunk[len(cutoff):]
        dot_idx     = search_area.find("."or ","or "؟"or "!"or "…")
        content     = cutoff + search_area[: dot_idx + 1] if dot_idx != -1 else chunk

        return content if content else None

    except Exception as exc:
        logger.warning(f"❌ Article content error: {exc}")
        return None



def extract_news(html: str, limit: int = 5) -> list[dict]:

    soup      = BeautifulSoup(html, "lxml")
    cards     = soup.find_all("div", class_="item-card")
    news_list: list[dict] = []

    for card in cards:
        if len(news_list) >= limit:
            break

        try:
            a_tag = card.find("a")
            if not a_tag:
                continue

            url = urljoin(BASE_URL, str(a_tag.get("href") or ""))
            if not url or url == BASE_URL:
                continue

            h3    = card.find("h3")
            title = clean_text(h3.get_text(strip=True)) if h3 else "بدون عنوان"

            if news_exists(url, title):
                continue

            img_tag     = card.find("img")
            raw_img_src: Optional[str] = None
            if img_tag:
                _src = img_tag.get("data-src") or img_tag.get("src")
                raw_img_src = str(_src) if _src is not None else None

            final_image = clean_image_url(raw_img_src)
            if final_image and "logo" in final_image.lower():
                final_image = None

            content = fetch_article_content(url)

            news_list.append({
                "title":   clean_text(title),
                "url":     url,
                "image":   final_image,
                "content": clean_text(content) if content else None,
            })

        except Exception as exc:
            logger.error(f"❌ Card parse error: {exc}")

    return news_list
