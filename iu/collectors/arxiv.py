from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)

# arXiv categories for AI/ML
ARXIV_CATEGORIES = [
    "cs.AI",   # Artificial Intelligence
    "cs.CL",   # Computation and Language (NLP)
    "cs.LG",   # Machine Learning
    "cs.CV",   # Computer Vision
    "cs.MA",   # Multiagent Systems
]

# Keywords to filter relevant papers
RELEVANT_KEYWORDS = [
    "agent", "llm", "language model", "transformer", "reasoning",
    "alignment", "safety", "reinforcement learning", "diffusion",
    "multimodal", "vision language", "code generation", "tool use",
    "rag", "retrieval", "fine-tuning", "rlhf", "chain of thought",
]


class ArxivCollector(BaseCollector):
    source = "arxiv"

    async def collect(self) -> list[RawItem]:
        items = []

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for category in ARXIV_CATEGORIES:
                try:
                    # Use arXiv RSS feed
                    rss_url = f"https://rss.arxiv.org/rss/{category}"
                    resp = await client.get(rss_url, headers={
                        "User-Agent": "InformationUnion/0.1"
                    })
                    if resp.status_code != 200:
                        logger.debug(f"arXiv {category}: HTTP {resp.status_code}")
                        continue

                    parsed = feedparser.parse(resp.text)

                    for entry in parsed.entries[:30]:
                        title = entry.get("title", "")
                        summary = entry.get("summary", "")
                        link = entry.get("link", "")

                        # Extract arXiv ID from link
                        arxiv_id = ""
                        match = re.search(r"(\d{4}\.\d{4,5})", link)
                        if match:
                            arxiv_id = match.group(1)

                        # Filter for relevant papers
                        text = f"{title} {summary}".lower()
                        if not any(kw in text for kw in RELEVANT_KEYWORDS):
                            continue

                        # Parse date
                        published = ""
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published = datetime(*entry.published_parsed[:6]).isoformat()
                            except Exception:
                                pass

                        # Clean summary
                        summary = re.sub(r"<[^>]+>", "", summary)[:2000]

                        items.append(RawItem(
                            source="arxiv",
                            source_url=link,
                            author=", ".join(a.get("name", "") for a in entry.get("authors", [])),
                            title=title.strip(),
                            content=summary,
                            published_at=published,
                            metadata={
                                "arxiv_id": arxiv_id,
                                "category": category,
                            },
                        ))

                    logger.info(f"arXiv {category}: {len([i for i in items if i.metadata.get('category') == category])} relevant papers")
                except Exception as e:
                    logger.warning(f"arXiv {category} failed: {e}")

        return items
