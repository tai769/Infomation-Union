from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema_companies.sql"


def init_company_tables(conn: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()


def seed_companies(conn: sqlite3.Connection) -> None:
    from iu.data.companies import COMPANIES
    for c in COMPANIES:
        conn.execute(
            """INSERT OR REPLACE INTO companies (id, name, ticker, layer, sub_layer, country, description, keywords)
               VALUES (?,?,?,?,?,?,?,?)""",
            (c["id"], c["name"], c.get("ticker", ""), c["layer"],
             c.get("sub_layer", ""), c.get("country", ""),
             c.get("description", ""), json.dumps(c.get("keywords", [])))
        )
    conn.commit()


def get_companies_by_layer(conn: sqlite3.Connection, layer: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM companies WHERE layer = ? ORDER BY name", (layer,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_companies(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM companies ORDER BY layer, name").fetchall()
    return [dict(r) for r in rows]


def get_company(conn: sqlite3.Connection, company_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    return dict(row) if row else None


def insert_impact_chain(conn: sqlite3.Connection, chain: dict) -> None:
    conn.execute(
        """INSERT INTO impact_chains (id, item_id, event_summary, affected_layers, created_at, week_start)
           VALUES (?,?,?,?,?,?)""",
        (chain["id"], chain.get("item_id", ""), chain["event_summary"],
         json.dumps(chain.get("affected_layers", [])),
         chain["created_at"], chain.get("week_start", ""))
    )
    conn.commit()


def insert_impact_detail(conn: sqlite3.Connection, detail: dict) -> None:
    conn.execute(
        """INSERT INTO impact_details (id, chain_id, company_id, impact_type, probability, timeline, reasoning, key_driver)
           VALUES (?,?,?,?,?,?,?,?)""",
        (detail["id"], detail["chain_id"], detail["company_id"],
         detail["impact_type"], detail.get("probability", 50),
         detail.get("timeline", ""), detail.get("reasoning", ""),
         detail.get("key_driver", ""))
    )


def get_impact_chains(conn: sqlite3.Connection, week_start: str = "") -> list[dict]:
    if week_start:
        rows = conn.execute(
            "SELECT * FROM impact_chains WHERE week_start = ? ORDER BY created_at DESC",
            (week_start,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM impact_chains ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def get_chain_details(conn: sqlite3.Connection, chain_id: str) -> list[dict]:
    rows = conn.execute("""
        SELECT d.*, c.name as company_name, c.ticker, c.layer as company_layer
        FROM impact_details d
        JOIN companies c ON d.company_id = c.id
        WHERE d.chain_id = ?
        ORDER BY d.probability DESC
    """, (chain_id,)).fetchall()
    return [dict(r) for r in rows]


def get_company_impacts(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    rows = conn.execute("""
        SELECT d.*, ic.event_summary, ic.created_at
        FROM impact_details d
        JOIN impact_chains ic ON d.chain_id = ic.id
        WHERE d.company_id = ?
        ORDER BY ic.created_at DESC
    """, (company_id,)).fetchall()
    return [dict(r) for r in rows]


def insert_breakthrough(conn: sqlite3.Connection, bt: dict) -> None:
    conn.execute(
        """INSERT INTO tech_breakthroughs (id, company_id, title, description, source_url, discovered_at, significance, layer)
           VALUES (?,?,?,?,?,?,?,?)""",
        (bt["id"], bt["company_id"], bt["title"], bt.get("description", ""),
         bt.get("source_url", ""), bt["discovered_at"],
         bt.get("significance", "medium"), bt.get("layer", ""))
    )
    conn.commit()


def get_breakthroughs(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute("""
        SELECT tb.*, c.name as company_name, c.ticker
        FROM tech_breakthroughs tb
        JOIN companies c ON tb.company_id = c.id
        ORDER BY tb.discovered_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]
