from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class TwitterCollector(BaseCollector):
    source = "twitter"

    async def collect(self) -> list[RawItem]:
        items = []
        persons = self.config.persons
        nitter_instances = self.config.twitter.nitter_instances

        if not nitter_instances:
            logger.warning("No Nitter instances configured")
            return items

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for person in persons:
                if not person.twitter:
                    continue

                for instance in nitter_instances:
                    try:
                        rss_url = f"{instance}/{person.twitter}/rss"
                        resp = await client.get(rss_url, headers={
                            "User-Agent": "InformationUnion/0.1"
                        })
                        if resp.status_code != 200:
                            continue

                        import feedparser
                        parsed = feedparser.parse(resp.text)

                        for entry in parsed.entries[:20]:
                            published = ""
                            if hasattr(entry, "published_parsed") and entry.published_parsed:
                                try:
                                    published = datetime(*entry.published_parsed[:6]).isoformat()
                                except Exception:
                                    pass

                            # Clean HTML from tweet content
                            content = self._clean_html(entry.get("summary", "") or entry.get("title", ""))

                            items.append(RawItem(
                                source="twitter",
                                source_url=entry.get("link", ""),
                                author=person.name,
                                author_handle=person.twitter,
                                title=content[:200],
                                content=content,
                                published_at=published,
                                person_id=person.id,
                            ))

                        logger.info(f"Twitter @{person.twitter}: {len(parsed.entries)} tweets from {instance}")
                        break  # Success, move to next person

                    except Exception as e:
                        logger.debug(f"Twitter @{person.twitter} via {instance} failed: {e}")
                        continue

        return items

    @staticmethod
    def _clean_html(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&\w+;", " ", text)
        return text.strip()
