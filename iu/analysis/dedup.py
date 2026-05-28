from __future__ import annotations

import json
import logging
import sqlite3
from difflib import SequenceMatcher
from datetime import datetime

logger = logging.getLogger(__name__)


def find_duplicates(items: list[dict], threshold: float = 0.6) -> list[list[int]]:
    """Find groups of duplicate items by title similarity.

    Returns list of groups, each group is a list of indices into items list.
    """
    n = len(items)
    # Union-Find for grouping
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Compare all pairs
    for i in range(n):
        for j in range(i + 1, n):
            t1 = (items[i].get("title", "") or "").lower()
            t2 = (items[j].get("title", "") or "").lower()

            if not t1 or not t2:
                continue

            # Quick check: if first 30 chars are very similar, likely duplicate
            if t1[:30] == t2[:30]:
                union(i, j)
                continue

            # Full similarity check
            sim = SequenceMatcher(None, t1, t2).ratio()
            if sim >= threshold:
                union(i, j)

    # Group by root
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Return only groups with more than 1 item
    return [g for g in groups.values() if len(g) > 1]


def deduplicate_items(conn: sqlite3.Connection, week_start: str = "", week_end: str = "") -> int:
    """Find and merge duplicate items. Returns count of merged groups."""
    if week_start and week_end:
        rows = conn.execute(
            "SELECT * FROM items WHERE published_at >= ? AND published_at <= ? ORDER BY importance DESC",
            (week_start, week_end + "T23:59:59")
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM items ORDER BY importance DESC").fetchall()

    items = [dict(r) for r in rows]
    if not items:
        return 0

    groups = find_duplicates(items, threshold=0.55)
    merged_count = 0

    for group_indices in groups:
        group_items = [items[i] for i in group_indices]

        # Sort by importance (highest first)
        group_items.sort(key=lambda x: x.get("importance", 0), reverse=True)

        primary = group_items[0]
        duplicates = group_items[1:]

        # Build merged metadata
        sources = list(set(d["source"] for d in group_items))
        source_urls = [d["source_url"] for d in group_items if d.get("source_url")]
        duplicate_ids = [d["id"] for d in duplicates]

        # Update primary item's metadata
        meta = json.loads(primary.get("metadata", "{}") or "{}")
        meta["merged_from"] = duplicate_ids
        meta["all_sources"] = sources
        meta["all_urls"] = source_urls[:5]  # Keep max 5 URLs
        meta["duplicate_count"] = len(duplicates)

        conn.execute(
            "UPDATE items SET metadata = ? WHERE id = ?",
            (json.dumps(meta), primary["id"])
        )

        # Mark duplicates
        for dup in duplicates:
            dup_meta = json.loads(dup.get("metadata", "{}") or "{}")
            dup_meta["merged_into"] = primary["id"]
            dup_meta["is_duplicate"] = True
            conn.execute(
                "UPDATE items SET metadata = ? WHERE id = ?",
                (json.dumps(dup_meta), dup["id"])
            )

        merged_count += 1
        if merged_count <= 5:
            logger.info(f"Merged: {primary['title'][:50]} ({len(duplicates)} duplicates)")

    conn.commit()
    logger.info(f"Deduplication: {merged_count} groups merged from {sum(len(g) for g in groups)} items")
    return merged_count


def get_deduplicated_items(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Get items with duplicates hidden (only show primary items)."""
    rows = conn.execute("""
        SELECT * FROM items
        WHERE metadata NOT LIKE '%"is_duplicate": true%'
        ORDER BY importance DESC, published_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")
        items.append(item)

    return items
