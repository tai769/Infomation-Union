from __future__ import annotations

import logging
import re
from datetime import datetime

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    source = "reddit"

    async def collect(self) -> list[RawItem]:
        items = []
        subreddits = self.config.reddit.subreddits

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for sub in subreddits:
                try:
                    # Use RSS feed instead of JSON API (Reddit blocks scrapers)
                    rss_url = f"https://www.reddit.com/r/{sub}/.rss?limit=25"
                    resp = await client.get(rss_url, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                    })
                    if resp.status_code != 200:
                        logger.warning(f"Reddit r/{sub}: HTTP {resp.status_code}")
                        continue

                    parsed = feedparser.parse(resp.text)

                    for entry in parsed.entries[:25]:
                        published = ""
                        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
                            try:
                                published = datetime(*entry.updated_parsed[:6]).isoformat()
                            except Exception:
                                pass

                        content = entry.get("summary", "") or entry.get("title", "")
                        # Clean HTML
                        content = re.sub(r"<[^>]+>", "", content)[:3000]

                        items.append(RawItem(
                            source="reddit",
                            source_url=entry.get("link", ""),
                            author=entry.get("author", "").replace("/u/", ""),
                            title=entry.get("title", ""),
                            content=content,
                            published_at=published,
                            metadata={"subreddit": sub},
                        ))

                    logger.info(f"Reddit r/{sub}: {len(parsed.entries)} posts via RSS")
                except Exception as e:
                    logger.warning(f"Reddit r/{sub} failed: {e}")

        return items
