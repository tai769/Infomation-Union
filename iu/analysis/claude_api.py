from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from iu.analysis.prompts import ANALYSIS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def analyze_items(items_data: dict, week_start: str, week_end: str,
                  api_key: str, model: str = "MiMo-V2.5-Pro",
                  max_tokens: int = 4096, base_url: str = "") -> dict:
    """Call LLM API to analyze intelligence items.

    Uses OpenAI-compatible protocol (works with MiMo, DeepSeek, etc.)
    """
    from jinja2 import Template
    from iu.analysis.prompts import ANALYSIS_USER_PROMPT

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    user_prompt = Template(ANALYSIS_USER_PROMPT).render(
        week_start=week_start,
        week_end=week_end,
        persons=items_data.get("persons", {}),
        products=items_data.get("products", {}),
        unlinked=items_data.get("unlinked", []),
    )

    # Truncate if too long
    if len(user_prompt) > 120000:
        logger.warning("Prompt too long, truncating unlinked items")
        items_data["unlinked"] = items_data.get("unlinked", [])[:10]
        user_prompt = Template(ANALYSIS_USER_PROMPT).render(
            week_start=week_start,
            week_end=week_end,
            persons=items_data.get("persons", {}),
            products=items_data.get("products", {}),
            unlinked=items_data.get("unlinked", []),
        )

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = response.choices[0].message.content

        # Try to extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text.strip())

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed, attempting recovery: {e}")
        # Try to recover partial JSON
        return _recover_json(text)
    except Exception as e:
        logger.error(f"API call failed: {e}")
        raise


def _recover_json(text: str) -> dict:
    """Attempt to recover partial JSON from a truncated response."""
    # Try to find week_summary
    summary_match = re.search(r'"week_summary"\s*:\s*"([^"]*)"', text)
    week_summary = summary_match.group(1) if summary_match else ""

    # Try to extract individual analyses
    analyses = []
    pattern = re.compile(
        r'"topic"\s*:\s*"([^"]*)".*?"summary"\s*:\s*"([^"]*)".*?"positive"\s*:\s*"([^"]*)".*?"negative"\s*:\s*"([^"]*)"',
        re.DOTALL
    )
    for m in pattern.finditer(text):
        analyses.append({
            "topic": m.group(1),
            "summary": m.group(2),
            "positive": m.group(3),
            "negative": m.group(4),
            "probability": {},
            "cross_validation": "",
        })

    if not analyses:
        # Fallback: just return raw text as summary
        return {"week_summary": text[:2000], "analyses": []}

    return {"week_summary": week_summary, "analyses": analyses}
