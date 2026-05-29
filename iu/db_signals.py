from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema_signals.sql"


def init_signal_tables(conn: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()


def insert_signal_chain(conn: sqlite3.Connection, chain: dict) -> None:
    conn.execute(
        """INSERT INTO signal_chains (id, topic, conclusion, confidence, signal_count, created_at, week_start, status)
           VALUES (?,?,?,?,?,?,?,?)""",
        (chain["id"], chain["topic"], chain["conclusion"],
         chain.get("confidence", 50), chain.get("signal_count", 0),
         chain["created_at"], chain.get("week_start", ""),
         chain.get("status", "active"))
    )
    conn.commit()


def insert_signal_chain_item(conn: sqlite3.Connection, chain_id: str, item_id: str,
                              role: str = "supporting", weight: int = 50) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO signal_chain_items (chain_id, item_id, signal_role, signal_weight) VALUES (?,?,?,?)",
        (chain_id, item_id, role, weight)
    )


def get_signal_chains(conn: sqlite3.Connection, week_start: str = "") -> list[dict]:
    if week_start:
        rows = conn.execute(
            "SELECT * FROM signal_chains WHERE week_start = ? ORDER BY confidence DESC",
            (week_start,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM signal_chains ORDER BY created_at DESC, confidence DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]


def get_chain_signals(conn: sqlite3.Connection, chain_id: str) -> list[dict]:
    rows = conn.execute("""
        SELECT sci.*, i.title, i.source, i.source_url, i.published_at, i.content
        FROM signal_chain_items sci
        JOIN items i ON sci.item_id = i.id
        WHERE sci.chain_id = ?
        ORDER BY sci.signal_weight DESC
    """, (chain_id,)).fetchall()
    return [dict(r) for r in rows]


def insert_company_tracking(conn: sqlite3.Connection, tracking: dict) -> None:
    conn.execute(
        """INSERT INTO company_tracking (id, company_id, period_start, period_end, summary, key_events, sentiment, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (tracking["id"], tracking["company_id"],
         tracking["period_start"], tracking["period_end"],
         tracking.get("summary", ""), json.dumps(tracking.get("key_events", [])),
         tracking.get("sentiment", "neutral"), tracking["created_at"])
    )
    conn.commit()


def insert_company_tracking_item(conn: sqlite3.Connection, tracking_id: str, item_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO company_tracking_items (tracking_id, item_id) VALUES (?,?)",
        (tracking_id, item_id)
    )


def get_company_trackings(conn: sqlite3.Connection, company_id: str = "") -> list[dict]:
    if company_id:
        rows = conn.execute("""
            SELECT ct.*, c.name as company_name, c.ticker
            FROM company_tracking ct JOIN companies c ON ct.company_id = c.id
            WHERE ct.company_id = ? ORDER BY ct.created_at DESC
        """, (company_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT ct.*, c.name as company_name, c.ticker
            FROM company_tracking ct JOIN companies c ON ct.company_id = c.id
            ORDER BY ct.created_at DESC LIMIT 30
        """).fetchall()
    return [dict(r) for r in rows]


def insert_heatmap(conn: sqlite3.Connection, entry: dict) -> None:
    conn.execute(
        """INSERT INTO industry_heatmap (id, sector, heat_score, trend, week_start, created_at, key_drivers, companies)
           VALUES (?,?,?,?,?,?,?,?)""",
        (entry["id"], entry["sector"], entry.get("heat_score", 50),
         entry.get("trend", "stable"), entry["week_start"],
         entry["created_at"], json.dumps(entry.get("key_drivers", [])),
         json.dumps(entry.get("companies", [])))
    )
    conn.commit()


def get_heatmap(conn: sqlite3.Connection, week_start: str = "") -> list[dict]:
    if week_start:
        rows = conn.execute(
            "SELECT * FROM industry_heatmap WHERE week_start = ? ORDER BY heat_score DESC",
            (week_start,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM industry_heatmap ORDER BY created_at DESC, heat_score DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]


def insert_viewpoint(conn: sqlite3.Connection, vp: dict) -> None:
    conn.execute(
        """INSERT INTO person_viewpoints (id, person_id, topic, viewpoint, sentiment, source_item_id, recorded_at, previous_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (vp["id"], vp["person_id"], vp["topic"], vp["viewpoint"],
         vp.get("sentiment", "neutral"), vp.get("source_item_id", ""),
         vp["recorded_at"], vp.get("previous_id", ""))
    )
    conn.commit()


def get_person_viewpoints(conn: sqlite3.Connection, person_id: str = "", topic: str = "") -> list[dict]:
    if person_id and topic:
        rows = conn.execute("""
            SELECT pv.*, p.name as person_name
            FROM person_viewpoints pv JOIN persons p ON pv.person_id = p.id
            WHERE pv.person_id = ? AND pv.topic = ?
            ORDER BY pv.recorded_at DESC
        """, (person_id, topic)).fetchall()
    elif person_id:
        rows = conn.execute("""
            SELECT pv.*, p.name as person_name
            FROM person_viewpoints pv JOIN persons p ON pv.person_id = p.id
            WHERE pv.person_id = ?
            ORDER BY pv.recorded_at DESC
        """, (person_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT pv.*, p.name as person_name
            FROM person_viewpoints pv JOIN persons p ON pv.person_id = p.id
            ORDER BY pv.recorded_at DESC LIMIT 30
        """).fetchall()
    return [dict(r) for r in rows]


def insert_competitive_group(conn: sqlite3.Connection, group: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO competitive_groups (id, name, description, companies)
           VALUES (?,?,?,?)""",
        (group["id"], group["name"], group.get("description", ""),
         json.dumps(group.get("companies", [])))
    )
    conn.commit()


def get_competitive_groups(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM competitive_groups ORDER BY name").fetchall()
    return [dict(r) for r in rows]
