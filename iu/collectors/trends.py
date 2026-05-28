from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)

# Keywords to track trends for
TRACKED_TOPICS = [
    "ai agent", "ai coding", "claude code", "cursor", "copilot", "codex",
    "chatgpt", "claude", "gemini", "llm", "gpt", "openai", "anthropic",
    "langchain", "crewai", "autogen", "nvidia", "gpu", "transformer",
    "reasoning", "agi", "alignment", "safety", "fine-tuning", "rag",
    "vector database", "embedding", "multimodal", "vision", "diffusion",
]


class TrendCollector(BaseCollector):
    """Tracks topic trends across HN and Reddit."""
    source = "trend"

    async def collect(self) -> list[RawItem]:
        items = []
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # Collect HN trends
            hn_current = await self._count_hn_topics(client, week_ago, now)
            hn_previous = await self._count_hn_topics(client, two_weeks_ago, week_ago)

            # Collect Reddit trends
            reddit_current = await self._count_reddit_topics(client, week_ago, now)

            # Generate trend report items
            trend_item = self._build_trend_report(hn_current, hn_previous, reddit_current)
            if trend_item:
                items.append(trend_item)

        return items

    async def _count_hn_topics(self, client: httpx.AsyncClient,
                                start: datetime, end: datetime) -> Counter:
        """Count topic mentions on HN via Algolia API."""
        counts = Counter()
        try:
            # Use Algolia HN search API
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                "tags": "story",
                "numericFilters": f"created_at_i>{int(start.timestamp())},created_at_i<{int(end.timestamp())}",
                "hitsPerPage": 500,
            }
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for hit in data.get("hits", []):
                title = (hit.get("title", "") or "").lower()
                for topic in TRACKED_TOPICS:
                    if topic in title:
                        counts[topic] += 1

            logger.info(f"HN trends: {sum(counts.values())} topic mentions from {len(data.get('hits', []))} stories")
        except Exception as e:
            logger.warning(f"HN trend counting failed: {e}")

        return counts

    async def _count_reddit_topics(self, client: httpx.AsyncClient,
                                    start: datetime, end: datetime) -> Counter:
        """Count topic mentions across AI subreddits."""
        counts = Counter()
        subreddits = ["MachineLearning", "artificial", "LocalLLaMA", "ChatGPT", "ClaudeAI"]

        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/r/{sub}/.rss?limit=100"
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                })
                if resp.status_code != 200:
                    continue

                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries:
                    title = (entry.get("title", "") or "").lower()
                    content = (entry.get("summary", "") or "").lower()
                    text = f"{title} {content}"

                    for topic in TRACKED_TOPICS:
                        if topic in text:
                            counts[topic] += 1

            except Exception as e:
                logger.debug(f"Reddit trend for r/{sub} failed: {e}")

        logger.info(f"Reddit trends: {sum(counts.values())} topic mentions")
        return counts

    def _build_trend_report(self, current: Counter, previous: Counter,
                            reddit: Counter) -> RawItem | None:
        """Build a trend summary item."""
        # Merge HN and Reddit counts
        combined = current + reddit

        if not combined:
            return None

        # Find top rising topics
        rising = []
        for topic, count in combined.most_common(10):
            prev_count = previous.get(topic, 0)
            if prev_count > 0:
                change = ((count - prev_count) / prev_count) * 100
                rising.append(f"{topic}: {count} mentions ({'+' if change > 0 else ''}{change:.0f}% vs last week)")
            else:
                rising.append(f"{topic}: {count} mentions (new this week)")

        content = "Top AI topics this week:\n" + "\n".join(rising)

        return RawItem(
            source="trend",
            source_url="",
            author="System",
            title=f"Weekly AI Topic Trends — {datetime.utcnow().strftime('%Y-%m-%d')}",
            content=content,
            published_at=datetime.utcnow().isoformat(),
            metadata={
                "top_topics": dict(combined.most_common(20)),
                "previous_topics": dict(previous.most_common(20)),
            },
        )
