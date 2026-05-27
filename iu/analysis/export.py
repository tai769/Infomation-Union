from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from jinja2 import Template

from iu.analysis.prompts import EXPORT_TEMPLATE
from iu.db import get_items_by_date, get_active_persons, get_active_products


def export_week(conn: sqlite3.Connection) -> str:
    """Export current week's items as structured Markdown."""
    today = datetime.utcnow()
    # Monday to Sunday
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%dT23:59:59")

    return _export_range(conn, start_str, end_str, week_start.strftime("%Y-%m-%d"), end_str)


def export_all(conn: sqlite3.Connection, limit: int = 200) -> str:
    """Export all recent items."""
    from iu.db import get_recent_items
    items = get_recent_items(conn, limit)
    return _format_items(conn, items, "All Time", "All Time")


def _export_range(conn: sqlite3.Connection, start: str, end: str,
                  week_start: str, week_end: str) -> str:
    items = get_items_by_date(conn, start, end)
    return _format_items(conn, items, week_start, week_end)


def _format_items(conn: sqlite3.Connection, items: list[dict],
                  week_start: str, week_end: str) -> str:
    persons = {p["id"]: p["name"] for p in get_active_persons(conn)}
    products = {p["id"]: p["name"] for p in get_active_products(conn)}

    # Group by person
    by_person: dict[str, list[dict]] = {}
    by_product: dict[str, list[dict]] = {}
    unlinked: list[dict] = []

    for item in items:
        pid = item.get("person_id")
        prid = item.get("product_id")

        if pid and pid in persons:
            name = persons[pid]
            by_person.setdefault(name, []).append(item)
        elif prid and prid in products:
            name = products[prid]
            by_product.setdefault(name, []).append(item)
        else:
            # Check mentions
            mentions = conn.execute(
                "SELECT entity_type, entity_id FROM item_mentions WHERE item_id=?",
                (item["id"],)
            ).fetchall()

            linked = False
            for m in mentions:
                if m["entity_type"] == "person" and m["entity_id"] in persons:
                    name = persons[m["entity_id"]]
                    by_person.setdefault(name, []).append(item)
                    linked = True
                    break
                elif m["entity_type"] == "product" and m["entity_id"] in products:
                    name = products[m["entity_id"]]
                    by_product.setdefault(name, []).append(item)
                    linked = True
                    break

            if not linked:
                unlinked.append(item)

    template = Template(EXPORT_TEMPLATE)
    return template.render(
        week_start=week_start,
        week_end=week_end,
        total=len(items),
        persons=by_person,
        products=by_product,
        unlinked=unlinked,
    )
