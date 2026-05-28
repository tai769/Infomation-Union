from __future__ import annotations

import logging
import re
from datetime import datetime

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)

# Popular AI-related Substack newsletters
SUBSTACK_FEEDS = [
    {"url": "https://www.latent.space/feed", "name": "Latent Space", "author": "Latent Space"},
    {"url": "https://buttondown.com/ainews/rss", "name": "AI News", "author": "AI News"},
    {"url": "https://samsnewsletter.substack.com/feed", "name": "Sam's Newsletter", "author": "Sam"},
    {"url": "https://thesequence.substack.com/feed", "name": "The Sequence", "author": "The Sequence"},
    {"url": "https://www.deeplearning.ai/the-batch/feed/", "name": "The Batch", "author": "Andrew Ng"},
    {"url": "https://ai-gaze.substack.com/feed", "name": "AI Gaze", "author": "AI Gaze"},
    {"url": "https://jack-clark.net/feed/", "name": "Import AI", "author": "Jack Clark"},
    {"url": "https://stratechery.com/feed/", "name": "Stratechery", "author": "Ben Thompson"},
]


class SubstackCollector(BaseCollector):
    source = "substack"

    async def collect(self) -> list[RawItem]:
        items = []

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for feed_cfg in SUBSTACK_FEEDS:
                try:
                    resp = await client.get(feed_cfg["url"], headers={
                        "User-Agent": "InformationUnion/0.1"
                    })
                    if resp.status_code != 200:
                        logger.debug(f"Substack [{feed_cfg['name']}]: HTTP {resp.status_code}")
                        continue

                    parsed = feedparser.parse(resp.text)

                    for entry in parsed.entries[:10]:
                        title = entry.get("title", "")
                        link = entry.get("link", "")

                        # Get content
                        content = ""
                        if hasattr(entry, "content") and entry.content:
                            content = entry.content[0].get("value", "")
                        elif hasattr(entry, "summary"):
                            content = entry.summary

                        # Clean HTML
                        content = re.sub(r"<[^>]+>", "", content)[:3000]

                        # Parse date
                        published = ""
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published = datetime(*entry.published_parsed[:6]).isoformat()
                            except Exception:
                                pass

                        if content.strip():
                            items.append(RawItem(
                                source="substack",
                                source_url=link,
                                author=feed_cfg["author"],
                                title=title,
                                content=content,
                                published_at=published,
                                metadata={"newsletter": feed_cfg["name"]},
                            ))

                    logger.info(f"Substack [{feed_cfg['name']}]: {len(parsed.entries)} entries")
                except Exception as e:
                    logger.debug(f"Substack [{feed_cfg['name']}] failed: {e}")

        return items
