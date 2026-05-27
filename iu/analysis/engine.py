from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta

from iu.config import AppConfig
from iu.db import (
    get_items_by_date, get_active_persons, get_active_products,
    insert_analysis, insert_report,
)

logger = logging.getLogger(__name__)


async def run_analysis(conn: sqlite3.Connection, config: AppConfig) -> None:
    """Run API analysis on the current week's data."""
    from iu.analysis.claude_api import analyze_items

    today = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%dT23:59:59")

    items = get_items_by_date(conn, start_str, end_str)
    if not items:
        logger.info("No items to analyze this week.")
        return

    items_data = _group_items(conn, items)
    logger.info(f"Analyzing {len(items)} items...")

    result = analyze_items(
        items_data=items_data,
        week_start=start_str,
        week_end=end_str,
        api_key=config.analysis.api_key,
        model=config.analysis.model,
        max_tokens=config.analysis.max_tokens,
        base_url=config.analysis.base_url,
    )

    # Store analyses
    now = datetime.utcnow().isoformat()
    analysis_ids = []

    for analysis in result.get("analyses", []):
        a_id = str(uuid.uuid4())

        # Try to find matching items by topic keywords
        topic = analysis.get("topic", "")
        matched_item_ids = _find_matching_items(items, topic)

        # Store one analysis per topic (link to best matching item if available)
        best_item_id = matched_item_ids[0] if matched_item_ids else None
        insert_analysis(conn, {
            "id": a_id,
            "item_id": best_item_id,
            "created_at": now,
            "method": "api",
            "model": config.analysis.model,
            "summary": analysis.get("summary", ""),
            "positive": analysis.get("positive", ""),
            "negative": analysis.get("negative", ""),
            "probability": analysis.get("probability", {}),
            "cross_validation": analysis.get("cross_validation", ""),
            "raw_response": json.dumps(analysis),
        })
        analysis_ids.append(a_id)

    # Store week summary
    week_summary = result.get("week_summary", "")
    if week_summary:
        report = {
            "id": str(uuid.uuid4()),
            "week_start": start_str,
            "week_end": end_str,
            "created_at": now,
            "summary": week_summary,
            "item_ids": [i["id"] for i in items],
            "analysis_ids": analysis_ids,
        }
        insert_report(conn, report)
        logger.info(f"Report generated with summary: {week_summary[:100]}...")

    logger.info(f"Stored {len(analysis_ids)} analyses.")
    return result


def _find_matching_items(items: list[dict], topic: str) -> list[str]:
    """Find items that match a topic by keyword matching."""
    if not topic:
        return []

    topic_lower = topic.lower()
    keywords = [w for w in topic_lower.split() if len(w) > 3]

    matched = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('content', '')}".lower()
        if any(kw in text for kw in keywords):
            matched.append(item["id"])

    return matched


async def generate_report(conn: sqlite3.Connection, config: AppConfig) -> dict:
    """Generate a weekly report."""
    today = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%dT23:59:59")

    items = get_items_by_date(conn, start_str, end_str)
    item_ids = [i["id"] for i in items]

    # Get analyses for these items
    analysis_ids = []
    rows = conn.execute("SELECT id FROM analyses ORDER BY created_at DESC LIMIT 50").fetchall()
    analysis_ids = [r["id"] for r in rows]

    report = {
        "id": str(uuid.uuid4()),
        "week_start": start_str,
        "week_end": end_str,
        "created_at": datetime.utcnow().isoformat(),
        "summary": f"Week of {start_str}: {len(items)} items collected, {len(analysis_ids)} analyses generated.",
        "item_ids": item_ids,
        "analysis_ids": analysis_ids,
    }

    insert_report(conn, report)
    logger.info(f"Report generated: {len(items)} items, {len(analysis_ids)} analyses")
    return report


def _group_items(conn: sqlite3.Connection, items: list[dict]) -> dict:
    """Group items by person/product for the analysis prompt."""
    persons = {p["id"]: p["name"] for p in get_active_persons(conn)}
    products = {p["id"]: p["name"] for p in get_active_products(conn)}

    by_person: dict[str, list[dict]] = {}
    by_product: dict[str, list[dict]] = {}
    unlinked: list[dict] = []

    for item in items:
        pid = item.get("person_id")
        prid = item.get("product_id")

        if pid and pid in persons:
            by_person.setdefault(persons[pid], []).append(item)
        elif prid and prid in products:
            by_product.setdefault(products[prid], []).append(item)
        else:
            unlinked.append(item)

    return {"persons": by_person, "products": by_product, "unlinked": unlinked}
