from __future__ import annotations

import logging
from datetime import datetime

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    source = "rss"

    async def collect(self) -> list[RawItem]:
        items = []
        feeds = self.config.rss.feeds

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for feed_cfg in feeds:
                try:
                    resp = await client.get(feed_cfg.url, headers={
                        "User-Agent": "InformationUnion/0.1"
                    })
                    resp.raise_for_status()
                    parsed = feedparser.parse(resp.text)

                    for entry in parsed.entries[:30]:  # Max 30 per feed
                        published = ""
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published = datetime(*entry.published_parsed[:6]).isoformat()
                            except Exception:
                                published = entry.get("published", "")

                        content = ""
                        if hasattr(entry, "summary"):
                            content = entry.summary
                        elif hasattr(entry, "content") and entry.content:
                            content = entry.content[0].get("value", "")

                        items.append(RawItem(
                            source="rss",
                            source_url=entry.get("link", ""),
                            author=feed_cfg.name or entry.get("author", ""),
                            title=entry.get("title", ""),
                            content=content,
                            published_at=published,
                        ))
                    logger.info(f"RSS [{feed_cfg.name}]: {len(parsed.entries)} entries")
                except Exception as e:
                    logger.warning(f"RSS [{feed_cfg.name}] failed: {e}")

        return items
