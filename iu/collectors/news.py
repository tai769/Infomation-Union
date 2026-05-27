from __future__ import annotations

import logging
from datetime import datetime

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class NewsCollector(BaseCollector):
    source = "news"

    async def collect(self) -> list[RawItem]:
        items = []

        # Google News RSS searches for tracked persons and products
        search_terms = self._build_search_terms()

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for term in search_terms:
                try:
                    encoded = term.replace(" ", "+")
                    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
                    resp = await client.get(url, headers={
                        "User-Agent": "InformationUnion/0.1"
                    })
                    resp.raise_for_status()
                    parsed = feedparser.parse(resp.text)

                    for entry in parsed.entries[:10]:
                        published = ""
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published = datetime(*entry.published_parsed[:6]).isoformat()
                            except Exception:
                                pass

                        source_name = ""
                        if hasattr(entry, "source") and hasattr(entry.source, "title"):
                            source_name = entry.source.title

                        items.append(RawItem(
                            source="news",
                            source_url=entry.get("link", ""),
                            author=source_name,
                            title=entry.get("title", ""),
                            content=entry.get("summary", "")[:2000],
                            published_at=published,
                        ))

                    logger.info(f"News [{term}]: {len(parsed.entries)} articles")
                except Exception as e:
                    logger.warning(f"News [{term}] failed: {e}")

        return items

    def _build_search_terms(self) -> list[str]:
        """Build search queries from tracked persons and products."""
        terms = []
        for person in self.config.persons[:8]:  # Limit queries
            terms.append(person.name)
        for product in self.config.products[:5]:
            terms.append(product.name)
        # Add some general AI terms
        terms.extend(["AI industry", "artificial intelligence startup"])
        return terms
