from __future__ import annotations

import logging
import re
from datetime import datetime

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class NewsletterCollector(BaseCollector):
    source = "newsletter"

    async def collect(self) -> list[RawItem]:
        items = []
        feeds = self.config.newsletter.feeds if hasattr(self.config, 'newsletter') else []

        if not feeds:
            # Default newsletter feeds
            feeds = [
                NewsletterFeed(url="https://stratechery.com/feed/", name="Stratechery", author="Ben Thompson"),
                NewsletterFeed(url="https://simonwillison.net/atom/everything/", name="Simon Willison", author="Simon Willison"),
                NewsletterFeed(url="https://www.latent.space/feed", name="Latent Space", author="Latent Space"),
                NewsletterFeed(url="https://buttondown.com/ainews/rss", name="AI News", author="AI News"),
            ]

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for feed_cfg in feeds:
                try:
                    resp = await client.get(feed_cfg.url, headers={
                        "User-Agent": "InformationUnion/0.1"
                    })
                    if resp.status_code != 200:
                        logger.debug(f"Newsletter [{feed_cfg.name}]: HTTP {resp.status_code}")
                        continue

                    parsed = feedparser.parse(resp.text)

                    for entry in parsed.entries[:10]:
                        published = ""
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published = datetime(*entry.published_parsed[:6]).isoformat()
                            except Exception:
                                pass

                        # Get content
                        content = ""
                        if hasattr(entry, "content") and entry.content:
                            content = entry.content[0].get("value", "")
                        elif hasattr(entry, "summary"):
                            content = entry.summary

                        # Clean HTML
                        content = re.sub(r"<[^>]+>", "", content)[:3000]

                        if content.strip():
                            items.append(RawItem(
                                source="newsletter",
                                source_url=entry.get("link", ""),
                                author=feed_cfg.author or feed_cfg.name,
                                title=entry.get("title", ""),
                                content=content,
                                published_at=published,
                                metadata={"newsletter": feed_cfg.name},
                            ))

                    logger.info(f"Newsletter [{feed_cfg.name}]: {len(parsed.entries)} entries")
                except Exception as e:
                    logger.warning(f"Newsletter [{feed_cfg.name}] failed: {e}")

        return items


class NewsletterFeed:
    def __init__(self, url: str, name: str = "", author: str = ""):
        self.url = url
        self.name = name
        self.author = author
