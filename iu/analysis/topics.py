from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta

from iu.config import AppConfig
from iu.db import insert_topic, link_item_topic

logger = logging.getLogger(__name__)

TOPIC_EXTRACTION_PROMPT = """Extract 8-10 major AI industry topics from the given items.

For each topic: name (short), summary (1-2 sentences), trend (rising/falling/stable), item_indices (which items belong to it, 0-indexed).

Topics should be specific themes like "AI Coding Tools" or "NVIDIA Strategy", NOT generic like "News".

Respond with JSON only:
{"topics": [{"name": "...", "summary": "...", "trend": "rising", "item_indices": [0,1,2]}]}"""


async def extract_topics(conn: sqlite3.Connection, config: AppConfig,
                          week_start: str, week_end: str) -> list[dict]:
    """Extract topics from this week's data using AI."""
    from openai import OpenAI

    client_kwargs = {"api_key": config.analysis.api_key}
    if config.analysis.base_url:
        client_kwargs["base_url"] = config.analysis.base_url
    client = OpenAI(**client_kwargs)

    # Get items for this week
    rows = conn.execute("""
        SELECT id, title, content, source, person_id
        FROM items
        WHERE published_at >= ? AND published_at <= ?
        ORDER BY importance DESC
        LIMIT 30
    """, (week_start, week_end + "T23:59:59")).fetchall()

    if not rows:
        logger.info("No items to extract topics from")
        return []

    # Build item list for prompt (short format)
    item_list = []
    for i, row in enumerate(rows):
        title = (row[1] or "")[:80]
        item_list.append(f"[{i}] [{row[3]}] {title}")

    items_text = "\n".join(item_list)

    try:
        response = client.chat.completions.create(
            model=config.analysis.model,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": TOPIC_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Items from {week_start} to {week_end}:\n\n{items_text}"},
            ],
        )

        text = response.choices[0].message.content

        # Parse JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())

        # Store topics and link items
        now = datetime.utcnow().isoformat()
        topics = []

        for topic_data in result.get("topics", []):
            topic_id = str(uuid.uuid4())
            topic = {
                "id": topic_id,
                "name": topic_data["name"],
                "summary": topic_data.get("summary", ""),
                "trend": topic_data.get("trend", "stable"),
                "week_start": week_start,
                "week_end": week_end,
                "created_at": now,
                "item_count": len(topic_data.get("item_indices", [])),
            }
            insert_topic(conn, topic)

            # Link items to topic
            for idx in topic_data.get("item_indices", []):
                if 0 <= idx < len(rows):
                    link_item_topic(conn, rows[idx][0], topic_id)

            topics.append(topic)
            logger.info(f"Topic: {topic['name']} ({topic['item_count']} items, {topic['trend']})")

        conn.commit()
        logger.info(f"Extracted {len(topics)} topics")
        return topics

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed for topics: {e}")
        return []
    except Exception as e:
        logger.error(f"Topic extraction failed: {e}")
        return []
