from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta

from iu.config import AppConfig
from iu.db_companies import (
    get_all_companies, insert_impact_chain, insert_impact_detail,
    insert_breakthrough,
)

logger = logging.getLogger(__name__)

IMPACT_ANALYSIS_PROMPT = """You are an AI industry chain analyst. Given a significant AI industry event, analyze its impact across the entire industry chain.

The industry chain has 6 layers:
1. Infrastructure (power, datacenter, optical, cooling)
2. Chip (GPU, ASIC, foundry, memory)
3. Cloud (hyperscalers)
4. Model (frontier models, open source)
5. Framework (agent frameworks, vector DB, MLOps)
6. Application (coding tools, agents, SaaS, autonomous, robotics)

For the given event, you must:
1. Identify which layers are affected
2. For each affected layer, identify specific companies
3. For each company, explain:
   - impact_type: positive/negative/neutral
   - probability: 0-100 (how likely this impact materializes)
   - timeline: immediate/1-3 months/3-6 months/6-12 months
   - reasoning: WHY this company is affected (the causal chain)
   - key_driver: the main factor driving the impact

4. Also check if the event indicates any technical breakthroughs for specific companies

Think in terms of CAUSAL CHAINS:
Event → Direct Impact → Second-order Effects → Company Impact

Example:
Event: "NVIDIA announces new B200 chip"
→ Direct: AI training costs drop 50%
→ Second-order: More companies can afford training → demand for cloud GPU increases
→ Company impacts:
  - NVIDIA: positive (more sales), probability 95%, immediate
  - AMD: negative (competitive pressure), probability 80%, 1-3 months
  - AWS/Azure/GCP: positive (more GPU cloud demand), probability 85%, 1-3 months
  - OpenAI/Anthropic: positive (lower training costs), probability 90%, immediate
  - Datacenter companies: positive (more infrastructure needed), probability 75%, 3-6 months

Respond in JSON:
{
  "affected_layers": ["chip", "cloud", "model"],
  "impacts": [
    {
      "company_id": "nvidia",
      "impact_type": "positive",
      "probability": 95,
      "timeline": "immediate",
      "reasoning": "Direct beneficiary as chip manufacturer...",
      "key_driver": "Increased demand for AI compute"
    }
  ],
  "breakthroughs": [
    {
      "company_id": "nvidia",
      "title": "B200 chip announcement",
      "description": "...",
      "significance": "high"
    }
  ]
}

Available company IDs: {company_ids}"""


async def analyze_impact(conn: sqlite3.Connection, config: AppConfig,
                          item: dict) -> dict | None:
    """Analyze the industry chain impact of a single item."""
    from openai import OpenAI

    client_kwargs = {"api_key": config.analysis.api_key}
    if config.analysis.base_url:
        client_kwargs["base_url"] = config.analysis.base_url
    client = OpenAI(**client_kwargs)

    companies = get_all_companies(conn)
    company_ids = [c["id"] for c in companies]
    company_map = {c["id"]: c for c in companies}

    title = item.get("title", "")
    content = (item.get("content", "") or "")[:1000]

    try:
        system_prompt = IMPACT_ANALYSIS_PROMPT.replace("{company_ids}", ", ".join(company_ids))

        response = client.chat.completions.create(
            model=config.analysis.model,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Event: {title}\n\nDetails: {content}"},
            ],
        )

        text = response.choices[0].message.content
        if not text:
            return None

        # Parse JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())

        # Store results
        now = datetime.utcnow().isoformat()
        today = datetime.utcnow()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

        chain_id = str(uuid.uuid4())
        insert_impact_chain(conn, {
            "id": chain_id,
            "item_id": item.get("id", ""),
            "event_summary": title,
            "affected_layers": result.get("affected_layers", []),
            "created_at": now,
            "week_start": week_start,
        })

        for impact in result.get("impacts", []):
            if impact.get("company_id") in company_map:
                insert_impact_detail(conn, {
                    "id": str(uuid.uuid4()),
                    "chain_id": chain_id,
                    "company_id": impact["company_id"],
                    "impact_type": impact.get("impact_type", "neutral"),
                    "probability": impact.get("probability", 50),
                    "timeline": impact.get("timeline", ""),
                    "reasoning": impact.get("reasoning", ""),
                    "key_driver": impact.get("key_driver", ""),
                })

        for bt in result.get("breakthroughs", []):
            if bt.get("company_id") in company_map:
                insert_breakthrough(conn, {
                    "id": str(uuid.uuid4()),
                    "company_id": bt["company_id"],
                    "title": bt.get("title", ""),
                    "description": bt.get("description", ""),
                    "source_url": item.get("source_url", ""),
                    "discovered_at": now,
                    "significance": bt.get("significance", "medium"),
                    "layer": company_map[bt["company_id"]].get("layer", ""),
                })

        conn.commit()
        logger.info(f"Impact analysis: {title[:50]} → {len(result.get('impacts', []))} companies affected")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed for impact analysis: {e}")
        return None
    except Exception as e:
        logger.error(f"Impact analysis failed: {e}")
        return None


async def analyze_week_impacts(conn: sqlite3.Connection, config: AppConfig,
                                limit: int = 10) -> list[dict]:
    """Analyze impact for the top items this week."""
    today = datetime.utcnow()
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

    # Get top items that haven't been analyzed yet
    rows = conn.execute("""
        SELECT i.* FROM items i
        LEFT JOIN impact_chains ic ON i.id = ic.item_id
        WHERE ic.id IS NULL
        AND i.importance >= 40
        ORDER BY i.importance DESC
        LIMIT ?
    """, (limit,)).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        result = await analyze_impact(conn, config, item)
        if result:
            results.append(result)

    logger.info(f"Analyzed impact for {len(results)} items")
    return results
