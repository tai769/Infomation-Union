"""Advanced analysis: signal chains, company tracking, heatmap, viewpoints, competitive comparison."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta

from iu.config import AppConfig
from iu.db_signals import (
    insert_signal_chain, insert_signal_chain_item,
    insert_company_tracking, insert_company_tracking_item,
    insert_heatmap, insert_viewpoint, insert_competitive_group,
    get_person_viewpoints,
)

logger = logging.getLogger(__name__)


SIGNAL_CHAIN_PROMPT = """Analyze these AI industry items and identify SIGNAL CHAINS - groups of related signals that together point to a larger conclusion.

A signal chain is: Signal A + Signal B + Signal C = Conclusion

For each chain provide:
- topic: What the chain is about (e.g., "Anthropic崛起", "AI编程格局变化")
- conclusion: The combined conclusion from these signals
- confidence: 0-100 how confident you are
- signals: which items (by index) form this chain, and their role (supporting/contradicting/context)

Respond in JSON:
{"chains": [{"topic": "...", "conclusion": "...", "confidence": 80, "signals": [{"idx": 0, "role": "supporting", "weight": 80}, ...]}]}"""


COMPANY_TRACKING_PROMPT = """For each of these AI companies, summarize what happened to them this week based on the items provided.

For each company:
- summary: 1-2 sentence summary of their week
- key_events: list of key events
- sentiment: positive/negative/neutral

Respond in JSON:
{"tracking": [{"company_id": "nvidia", "summary": "...", "key_events": ["event1", "event2"], "sentiment": "positive"}]}"""


HEATMAP_PROMPT = """Analyze these AI industry items and create an INDUSTRY HEATMAP showing how hot each AI sector is this week.

Sectors: AI编程, AI Agent, AI芯片, AI基础设施, AI模型, AI安全, 自动驾驶, AI机器人, AI SaaS

For each sector:
- heat_score: 0-100 (how much activity/attention this week)
- trend: rising/falling/stable
- key_drivers: what's driving the heat
- companies: which company_ids are most active in this sector

Respond in JSON:
{"sectors": [{"sector": "AI编程", "heat_score": 85, "trend": "rising", "key_drivers": ["Cursor融资", "Copilot更新"], "companies": ["cursor", "github", "replit"]}]}"""


VIEWPOINT_PROMPT = """Extract VIEWPOINTS from these items - what specific people think about specific topics.

For each viewpoint:
- person_id: the person's ID
- topic: what they're talking about (e.g., "AI Agent", "AI安全", "AI编程")
- viewpoint: what they said/think (1-2 sentences)
- sentiment: optimistic/cautious/pessimistic

Respond in JSON:
{"viewpoints": [{"person_id": "karpathy", "topic": "AI Agent", "viewpoint": "Agents will replace most SaaS", "sentiment": "optimistic"}]}"""


COMPETITIVE_COMPARISON_PROMPT = """Create competitive comparisons for these AI product groups.

Groups to analyze:
- AI编程: claude-code, codex, cursor, copilot, replit, codeium
- 大模型: openai, anthropic, google-ai, meta-ai, xai, mistral
- Agent框架: langchain, crewai, autogen, huggingface
- AI芯片: nvidia, amd, intel, cerebras, groq

For each group, compare the companies based on this week's items. Include:
- Position/ranking this week
- Key developments
- Strengths/weaknesses
- Trend direction

Respond in JSON:
{"comparisons": [{"group": "AI编程", "entries": [{"company_id": "cursor", "position": 1, "key_dev": "...", "trend": "rising"}]}]}"""


async def run_advanced_analysis(conn: sqlite3.Connection, config: AppConfig) -> dict:
    """Run all 5 advanced analyses."""
    from openai import OpenAI

    client_kwargs = {"api_key": config.analysis.api_key}
    if config.analysis.base_url:
        client_kwargs["base_url"] = config.analysis.base_url
    client = OpenAI(**client_kwargs)

    today = datetime.utcnow()
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    week_end = (today + timedelta(days=6 - today.weekday())).strftime("%Y-%m-%d")

    # Get this week's items
    rows = conn.execute("""
        SELECT id, title, content, source, person_id, product_id
        FROM items WHERE published_at >= ? AND published_at <= ?
        ORDER BY importance DESC LIMIT 40
    """, (week_start, week_end + "T23:59:59")).fetchall()

    if not rows:
        logger.info("No items for advanced analysis")
        return {}

    items = [dict(r) for r in rows]
    item_list = "\n".join(
        f"[{i}] [{r['source']}] {r['title'][:80]}"
        for i, r in enumerate(items)
    )

    now = datetime.utcnow().isoformat()
    results = {}

    # 1. Signal Chains
    try:
        resp = client.chat.completions.create(
            model=config.analysis.model, max_tokens=8192,
            messages=[
                {"role": "system", "content": SIGNAL_CHAIN_PROMPT},
                {"role": "user", "content": item_list},
            ],
        )
        text = resp.choices[0].message.content
        if text:
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            # Try to fix common JSON issues
            text = text.strip()
            if not text.endswith("}"):
                # Find last complete object
                last_brace = text.rfind("}")
                if last_brace > 0:
                    text = text[:last_brace + 1]
                    # Count braces to fix nesting
                    open_count = text.count("{")
                    close_count = text.count("}")
                    text += "}" * (open_count - close_count)
                    if not text.endswith("]}"):
                        text += "]}"
            data = json.loads(text)
            for chain_data in data.get("chains", []):
                chain_id = str(uuid.uuid4())
                insert_signal_chain(conn, {
                    "id": chain_id, "topic": chain_data["topic"],
                    "conclusion": chain_data["conclusion"],
                    "confidence": chain_data.get("confidence", 50),
                    "signal_count": len(chain_data.get("signals", [])),
                    "created_at": now, "week_start": week_start,
                })
                for sig in chain_data.get("signals", []):
                    idx = sig.get("idx", 0)
                    if 0 <= idx < len(items):
                        insert_signal_chain_item(conn, chain_id, items[idx]["id"],
                                                  sig.get("role", "supporting"),
                                                  sig.get("weight", 50))
            conn.commit()
            results["signal_chains"] = len(data.get("chains", []))
            logger.info(f"Signal chains: {results['signal_chains']}")
    except Exception as e:
        logger.warning(f"Signal chain analysis failed: {e}")

    # 2. Company Tracking
    try:
        companies = conn.execute("SELECT id, name FROM companies WHERE active=1").fetchall()
        company_list = ", ".join(f"{c['id']}({c['name']})" for c in companies[:30])

        resp = client.chat.completions.create(
            model=config.analysis.model, max_tokens=8192,
            messages=[
                {"role": "system", "content": COMPANY_TRACKING_PROMPT},
                {"role": "user", "content": f"Companies: {company_list}\n\nItems:\n{item_list}"},
            ],
        )
        text = resp.choices[0].message.content
        if text:
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            data = json.loads(text.strip())
            for t in data.get("tracking", []):
                insert_company_tracking(conn, {
                    "id": str(uuid.uuid4()), "company_id": t["company_id"],
                    "period_start": week_start, "period_end": week_end,
                    "summary": t.get("summary", ""),
                    "key_events": t.get("key_events", []),
                    "sentiment": t.get("sentiment", "neutral"),
                    "created_at": now,
                })
            conn.commit()
            results["company_tracking"] = len(data.get("tracking", []))
            logger.info(f"Company tracking: {results['company_tracking']}")
    except Exception as e:
        logger.warning(f"Company tracking failed: {e}")

    # 3. Heatmap
    try:
        resp = client.chat.completions.create(
            model=config.analysis.model, max_tokens=4096,
            messages=[
                {"role": "system", "content": HEATMAP_PROMPT},
                {"role": "user", "content": item_list},
            ],
        )
        text = resp.choices[0].message.content
        if text:
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            data = json.loads(text.strip())
            for s in data.get("sectors", []):
                insert_heatmap(conn, {
                    "id": str(uuid.uuid4()), "sector": s["sector"],
                    "heat_score": s.get("heat_score", 50),
                    "trend": s.get("trend", "stable"),
                    "week_start": week_start, "created_at": now,
                    "key_drivers": s.get("key_drivers", []),
                    "companies": s.get("companies", []),
                })
            conn.commit()
            results["heatmap"] = len(data.get("sectors", []))
            logger.info(f"Heatmap: {results['heatmap']} sectors")
    except Exception as e:
        logger.warning(f"Heatmap analysis failed: {e}")

    # 4. Viewpoints
    try:
        resp = client.chat.completions.create(
            model=config.analysis.model, max_tokens=4096,
            messages=[
                {"role": "system", "content": VIEWPOINT_PROMPT},
                {"role": "user", "content": item_list},
            ],
        )
        text = resp.choices[0].message.content
        if text:
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            data = json.loads(text.strip())
            for vp in data.get("viewpoints", []):
                # Check if person exists
                person = conn.execute("SELECT id FROM persons WHERE id = ?", (vp["person_id"],)).fetchone()
                if not person:
                    continue

                # Find previous viewpoint on same topic
                prev = get_person_viewpoints(conn, vp["person_id"], vp.get("topic", ""))
                prev_id = prev[0]["id"] if prev else ""

                insert_viewpoint(conn, {
                    "id": str(uuid.uuid4()), "person_id": vp["person_id"],
                    "topic": vp.get("topic", ""), "viewpoint": vp["viewpoint"],
                    "sentiment": vp.get("sentiment", "neutral"),
                    "recorded_at": now, "previous_id": prev_id,
                })
            conn.commit()
            results["viewpoints"] = len(data.get("viewpoints", []))
            logger.info(f"Viewpoints: {results['viewpoints']}")
    except Exception as e:
        logger.warning(f"Viewpoint analysis failed: {e}")

    # 5. Competitive Comparison
    try:
        resp = client.chat.completions.create(
            model=config.analysis.model, max_tokens=8192,
            messages=[
                {"role": "system", "content": COMPETITIVE_COMPARISON_PROMPT},
                {"role": "user", "content": item_list},
            ],
        )
        text = resp.choices[0].message.content
        if text:
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            data = json.loads(text.strip())
            for comp in data.get("comparisons", []):
                insert_competitive_group(conn, {
                    "id": str(uuid.uuid4()), "name": comp["group"],
                    "description": json.dumps(comp.get("entries", [])),
                    "companies": [e.get("company_id", "") for e in comp.get("entries", [])],
                })
            conn.commit()
            results["competitive"] = len(data.get("comparisons", []))
            logger.info(f"Competitive groups: {results['competitive']}")
    except Exception as e:
        logger.warning(f"Competitive comparison failed: {e}")

    return results
