from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta

from iu.db import get_active_persons, get_active_products

logger = logging.getLogger(__name__)

# Source authority weights (0-100)
SOURCE_WEIGHTS = {
    "newsletter": 90,   # Curated by experts
    "substack": 85,     # In-depth analysis
    "rss": 80,          # Official blogs
    "github": 75,       # Actual code activity
    "youtube": 70,      # Video content
    "news": 65,         # News articles
    "arxiv": 60,        # Research papers
    "reddit": 50,       # Community discussion
    "twitter": 55,      # Social media
    "producthunt": 45,  # Product launches
    "trend": 40,        # Aggregated trends
}

# Person importance weights
PERSON_WEIGHTS = {
    "karpathy": 95,
    "sam-altman": 95,
    "dario-amodei": 90,
    "jensen-huang": 90,
    "ilya-sutskever": 85,
    "harrison-chase": 75,
    "guillermo-rauch": 70,
    "amjad-masad": 70,
    "theo-browne": 60,
    "lex-fridman": 80,
    "ben-thompson": 75,
    "matt-wolfe": 60,
    "ai-jason": 55,
    "logan-kilpatrick": 65,
}


def score_item(item: dict, persons: list[dict], products: list[dict]) -> int:
    """Calculate importance score (0-100) for an item."""
    score = 0

    # 1. Source weight (0-20 points)
    source = item.get("source", "")
    source_score = SOURCE_WEIGHTS.get(source, 30)
    score += int(source_score * 0.20)

    # 2. Person weight (0-35 points)
    person_id = item.get("person_id", "")
    if person_id:
        person_score = PERSON_WEIGHTS.get(person_id, 40)
        score += int(person_score * 0.35)
    else:
        person_score = _get_mention_score(item, persons)
        score += int(person_score * 0.30)

    # 3. Timeliness (0-20 points)
    published = item.get("published_at", "")
    if published:
        try:
            pub_date = datetime.fromisoformat(published.replace("Z", "+00:00").replace(tzinfo=None))
            days_old = (datetime.utcnow() - pub_date).days
            if days_old <= 1:
                score += 20
            elif days_old <= 3:
                score += 15
            elif days_old <= 7:
                score += 10
            elif days_old <= 14:
                score += 5
        except (ValueError, TypeError):
            pass

    # 4. Content quality signals (0-15 points)
    content = item.get("content", "")
    title = item.get("title", "")
    text = f"{title} {content}".lower()

    important_keywords = [
        "announce", "launch", "release", "funding", "acquisition",
        "partnership", "breaking", "exclusive", "joins", "raises",
        "announce", "发布", "融资", "收购", "合作", "加入",
    ]
    keyword_hits = sum(1 for kw in important_keywords if kw in text)
    score += min(keyword_hits * 4, 15)

    # 5. Product mention boost (0-10 points)
    product_id = item.get("product_id", "")
    if product_id:
        score += 10

    # 6. Mention count boost (0-10 points)
    # Items that mention multiple tracked entities are more important
    text = f"{title} {content}".lower()
    entity_count = 0
    for person in persons:
        if person.get("name", "").lower() in text:
            entity_count += 1
    for product in products:
        if product.get("name", "").lower() in text:
            entity_count += 1
    score += min(entity_count * 3, 10)

    return min(score, 100)


def _get_mention_score(item: dict, persons: list[dict]) -> int:
    """Get score based on mentioned persons."""
    text = f"{item.get('title', '')} {item.get('content', '')}".lower()
    max_score = 0

    for person in persons:
        name = person.get("name", "").lower()
        if name and name in text:
            person_id = person.get("id", "")
            score = PERSON_WEIGHTS.get(person_id, 40)
            max_score = max(max_score, score)

    return max_score


def score_all_items(conn: sqlite3.Connection) -> int:
    """Score all items in the database. Returns count of scored items."""
    persons = get_active_persons(conn)
    products = get_active_products(conn)

    rows = conn.execute("SELECT * FROM items").fetchall()
    scored = 0

    for row in rows:
        item = dict(row)
        importance = score_item(item, persons, products)
        conn.execute("UPDATE items SET importance = ? WHERE id = ?", (importance, item["id"]))
        scored += 1

    conn.commit()
    logger.info(f"Scored {scored} items")
    return scored
