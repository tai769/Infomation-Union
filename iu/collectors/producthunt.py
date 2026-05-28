from __future__ import annotations

import logging
import re
from datetime import datetime

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class ProductHuntCollector(BaseCollector):
    source = "producthunt"

    async def collect(self) -> list[RawItem]:
        items = []

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                # Product Hunt has an RSS feed
                resp = await client.get("https://www.producthunt.com/feed", headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                })
                if resp.status_code != 200:
                    logger.warning(f"Product Hunt: HTTP {resp.status_code}")
                    return items

                parsed = feedparser.parse(resp.text)

                for entry in parsed.entries[:30]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "") or entry.get("description", "")
                    link = entry.get("link", "")

                    # Clean HTML
                    summary = re.sub(r"<[^>]+>", "", summary)[:2000]

                    # Parse date
                    published = ""
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6]).isoformat()
                        except Exception:
                            pass

                    items.append(RawItem(
                        source="producthunt",
                        source_url=link,
                        author="Product Hunt",
                        title=title,
                        content=summary,
                        published_at=published,
                    ))

                logger.info(f"Product Hunt: {len(items)} products")
            except Exception as e:
                logger.warning(f"Product Hunt failed: {e}")

        return items
