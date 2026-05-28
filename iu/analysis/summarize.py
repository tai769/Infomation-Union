from __future__ import annotations

import json
import logging
import sqlite3

from iu.analysis.prompts import YOUTUBE_SUMMARIZE_PROMPT
from iu.config import AppConfig

logger = logging.getLogger(__name__)


async def summarize_youtube(conn: sqlite3.Connection, config: AppConfig, limit: int = 20) -> int:
    """Summarize YouTube video transcripts that haven't been summarized yet."""
    from openai import OpenAI

    client_kwargs = {"api_key": config.analysis.api_key}
    if config.analysis.base_url:
        client_kwargs["base_url"] = config.analysis.base_url
    client = OpenAI(**client_kwargs)

    # Get YouTube items without summary in metadata
    rows = conn.execute("""
        SELECT id, title, content, source_url, metadata
        FROM items
        WHERE source = 'youtube' AND content != ''
        ORDER BY published_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

    summarized = 0
    for row in rows:
        item_id = row[0]
        title = row[1]
        content = row[2]
        meta = json.loads(row[4] or "{}")

        # Skip if already summarized
        if meta.get("summary"):
            continue

        if len(content) < 200:
            continue

        try:
            # Truncate long transcripts
            transcript = content[:8000] if len(content) > 8000 else content

            response = client.chat.completions.create(
                model=config.analysis.model,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": YOUTUBE_SUMMARIZE_PROMPT},
                    {"role": "user", "content": f"Video title: {title}\n\nTranscript:\n{transcript}"},
                ],
            )

            text = response.choices[0].message.content

            # Parse JSON response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            summary_data = json.loads(text.strip())

            # Update item metadata with summary
            meta["summary"] = summary_data
            conn.execute(
                "UPDATE items SET metadata = ? WHERE id = ?",
                (json.dumps(meta), item_id)
            )
            conn.commit()

            summarized += 1
            logger.info(f"Summarized: {title[:50]}")

        except json.JSONDecodeError:
            # Store raw text as summary
            meta["summary"] = {"title": title, "key_points": [text[:300]]}
            conn.execute("UPDATE items SET metadata = ? WHERE id = ?", (json.dumps(meta), item_id))
            conn.commit()
            summarized += 1
        except Exception as e:
            logger.warning(f"Failed to summarize {title[:30]}: {e}")

    logger.info(f"Summarized {summarized} YouTube videos")
    return summarized
