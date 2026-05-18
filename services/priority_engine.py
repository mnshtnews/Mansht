import time
from typing import Optional
from config.settings import KEYWORD_PRIORITY, AGING_MULTIPLIER
from services.ai_ranking import calculate_ai_score


def calculate_keyword_score(text: str) -> int:
    score = 0
    for priority, keywords in KEYWORD_PRIORITY.items():
        for kw in keywords:
            if kw in text:
                score += priority
    return score


def calculate_aging_bonus(created_at: float, now: Optional[float] = None) -> float:
    if now is None:
        now = time.time()
    age_minutes = (now - created_at) / 60
    return age_minutes * AGING_MULTIPLIER


def calculate_final_score(title: str, content: str, created_at: float) -> dict:
    text = f"{title} {content or ''}"

    ai_score      = calculate_ai_score(title, content)
    keyword_score = calculate_keyword_score(text)
    aging_score   = calculate_aging_bonus(created_at)
    final_score   = keyword_score + aging_score + ai_score

    return {
        "keyword_score": keyword_score,
        "aging_score":   aging_score,
        "ai_score":      ai_score,
        "final_score":   final_score,
    }
