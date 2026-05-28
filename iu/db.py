from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "iu.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()


def compute_hash(source: str, source_url: str) -> str:
    return hashlib.sha256(f"{source}:{source_url}".encode()).hexdigest()


def insert_person(conn: sqlite3.Connection, person_id: str, name: str,
                  twitter: str = "", youtube: str = "", reddit: str = "",
                  github: str = "", tags: list[str] | None = None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO persons (id, name, twitter, youtube, reddit, github, tags) VALUES (?,?,?,?,?,?,?)",
        (person_id, name, twitter, youtube, reddit, github, json.dumps(tags or []))
    )
    conn.commit()


def insert_product(conn: sqlite3.Connection, product_id: str, name: str,
                   company: str = "", tags: list[str] | None = None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO products (id, name, company, tags) VALUES (?,?,?,?)",
        (product_id, name, company, json.dumps(tags or []))
    )
    conn.commit()


def item_exists(conn: sqlite3.Connection, content_hash: str) -> bool:
    row = conn.execute("SELECT 1 FROM items WHERE content_hash=?", (content_hash,)).fetchone()
    return row is not None


def insert_item(conn: sqlite3.Connection, item_id: str, source: str, source_url: str,
                content_hash: str, author: str = "", author_handle: str = "",
                title: str = "", content: str = "", published_at: str = "",
                collected_at: str = "", media_urls: list[str] | None = None,
                metadata: dict | None = None, person_id: str | None = None,
                product_id: str | None = None) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO items
           (id, source, source_url, author, author_handle, title, content,
            published_at, collected_at, media_urls, metadata, person_id, product_id, content_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (item_id, source, source_url, author, author_handle, title, content,
         published_at, collected_at, json.dumps(media_urls or []),
         json.dumps(metadata or {}), person_id, product_id, content_hash)
    )
    conn.commit()


def add_mention(conn: sqlite3.Connection, item_id: str, entity_type: str, entity_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO item_mentions (item_id, entity_type, entity_id) VALUES (?,?,?)",
        (item_id, entity_type, entity_id)
    )


def get_active_persons(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM persons WHERE active=1").fetchall()
    return [dict(r) for r in rows]


def get_active_products(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM products WHERE active=1").fetchall()
    return [dict(r) for r in rows]


def get_items_by_date(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM items WHERE published_at >= ? AND published_at <= ? ORDER BY published_at DESC",
        (start, end)
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_items(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM items ORDER BY collected_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_items_by_person(conn: sqlite3.Connection, person_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM items WHERE person_id = ?
           OR id IN (SELECT item_id FROM item_mentions WHERE entity_type='person' AND entity_id=?)
           ORDER BY published_at DESC""",
        (person_id, person_id)
    ).fetchall()
    return [dict(r) for r in rows]


def get_items_by_product(conn: sqlite3.Connection, product_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM items WHERE product_id = ?
           OR id IN (SELECT item_id FROM item_mentions WHERE entity_type='product' AND entity_id=?)
           ORDER BY published_at DESC""",
        (product_id, product_id)
    ).fetchall()
    return [dict(r) for r in rows]


def search_items(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT i.* FROM items i
           JOIN items_fts f ON i.rowid = f.rowid
           WHERE items_fts MATCH ? ORDER BY rank LIMIT ?""",
        (query, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def insert_analysis(conn: sqlite3.Connection, analysis: dict) -> None:
    conn.execute(
        """INSERT INTO analyses (id, item_id, created_at, method, model,
           summary, positive, negative, probability, cross_validation, raw_response)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (analysis["id"], analysis["item_id"], analysis["created_at"],
         analysis["method"], analysis.get("model", ""),
         analysis.get("summary", ""), analysis.get("positive", ""),
         analysis.get("negative", ""), json.dumps(analysis.get("probability", {})),
         analysis.get("cross_validation", ""), analysis.get("raw_response", ""))
    )
    conn.commit()


def insert_report(conn: sqlite3.Connection, report: dict) -> None:
    conn.execute(
        """INSERT INTO reports (id, week_start, week_end, created_at, summary,
           item_ids, analysis_ids, delivered_email, delivered_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (report["id"], report["week_start"], report["week_end"],
         report["created_at"], report.get("summary", ""),
         json.dumps(report.get("item_ids", [])),
         json.dumps(report.get("analysis_ids", [])),
         1 if report.get("delivered_email") else 0,
         report.get("delivered_at", ""))
    )
    conn.commit()


def get_latest_report(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def get_item_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()
    return row["cnt"]


def get_person_item_counts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT p.id, p.name, (
            SELECT COUNT(DISTINCT i.id) FROM items i
            WHERE i.person_id = p.id
               OR i.id IN (SELECT m.item_id FROM item_mentions m WHERE m.entity_type = 'person' AND m.entity_id = p.id)
        ) as count
        FROM persons p
        WHERE p.active = 1
        ORDER BY count DESC
    """).fetchall()
    return [dict(r) for r in rows]


def update_item_importance(conn: sqlite3.Connection, item_id: str, importance: int) -> None:
    conn.execute("UPDATE items SET importance = ? WHERE id = ?", (importance, item_id))


def get_top_items(conn: sqlite3.Connection, limit: int = 10, week_start: str = "") -> list[dict]:
    if week_start:
        rows = conn.execute(
            "SELECT * FROM items WHERE published_at >= ? ORDER BY importance DESC, published_at DESC LIMIT ?",
            (week_start, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY importance DESC, published_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def insert_topic(conn: sqlite3.Connection, topic: dict) -> None:
    conn.execute(
        """INSERT INTO topics (id, name, summary, trend, week_start, week_end, created_at, item_count)
           VALUES (?,?,?,?,?,?,?,?)""",
        (topic["id"], topic["name"], topic.get("summary", ""),
         topic.get("trend", ""), topic["week_start"], topic["week_end"],
         topic["created_at"], topic.get("item_count", 0))
    )
    conn.commit()


def link_item_topic(conn: sqlite3.Connection, item_id: str, topic_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO item_topics (item_id, topic_id) VALUES (?,?)",
        (item_id, topic_id)
    )


def get_topics(conn: sqlite3.Connection, week_start: str = "") -> list[dict]:
    if week_start:
        rows = conn.execute(
            "SELECT * FROM topics WHERE week_start = ? ORDER BY item_count DESC",
            (week_start,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM topics ORDER BY created_at DESC, item_count DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def get_topic_items(conn: sqlite3.Connection, topic_id: str) -> list[dict]:
    rows = conn.execute("""
        SELECT i.* FROM items i
        JOIN item_topics it ON i.id = it.item_id
        WHERE it.topic_id = ?
        ORDER BY i.importance DESC, i.published_at DESC
    """, (topic_id,)).fetchall()
    return [dict(r) for r in rows]
