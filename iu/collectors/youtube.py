from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

import feedparser
import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 30


class YouTubeCollector(BaseCollector):
    source = "youtube"

    async def collect(self) -> list[RawItem]:
        items = []
        persons = [p for p in self.config.persons if p.youtube_channel]

        if not persons:
            return items

        cutoff = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for person in persons:
                try:
                    videos = await self._get_rss_videos(client, person.youtube_channel)
                    recent_count = 0

                    for vid in videos:
                        if vid["published"] < cutoff:
                            continue

                        recent_count += 1
                        subtitle_text = self._extract_subtitles(vid["id"])

                        items.append(RawItem(
                            source="youtube",
                            source_url=f"https://www.youtube.com/watch?v={vid['id']}",
                            author=person.name,
                            author_handle=person.youtube_channel,
                            title=vid.get("title", ""),
                            content=subtitle_text[:5000] if subtitle_text else vid.get("summary", "")[:1000],
                            published_at=vid["published"].isoformat(),
                            metadata={"video_id": vid["id"]},
                            person_id=person.id,
                        ))
                        logger.info(f"YouTube [{person.name}]: {vid['title'][:50]} ({vid['published'].strftime('%Y-%m-%d')})")

                    logger.info(f"YouTube [{person.name}]: {recent_count} videos in last {LOOKBACK_DAYS} days")
                except Exception as e:
                    logger.warning(f"YouTube [{person.name}] failed: {e}")

        return items

    async def _get_rss_videos(self, client: httpx.AsyncClient, channel_id: str) -> list[dict]:
        """Get videos from YouTube RSS feed (includes publish dates)."""
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        resp = await client.get(rss_url)
        resp.raise_for_status()

        # Parse with feedparser
        parsed = feedparser.parse(resp.text)
        videos = []

        for entry in parsed.entries:
            # Extract video ID from yt:videoId
            vid_id = entry.get("yt_videoid", "")
            if not vid_id:
                # Try to extract from link
                link = entry.get("link", "")
                match = re.search(r"v=([^&]+)", link)
                if match:
                    vid_id = match.group(1)

            if not vid_id:
                continue

            # Parse publish date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            if not published:
                continue

            videos.append({
                "id": vid_id,
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "published": published,
            })

        return videos

    def _extract_subtitles(self, video_id: str) -> str:
        """Extract subtitles using yt-dlp."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    "yt-dlp",
                    "--write-auto-sub", "--write-sub",
                    "--sub-lang", "en",
                    "--skip-download",
                    "--sub-format", "vtt",
                    "-o", f"{tmpdir}/%(id)s",
                    f"https://www.youtube.com/watch?v={video_id}",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                for f in Path(tmpdir).glob("*.vtt"):
                    text = f.read_text(encoding="utf-8")
                    return self._parse_vtt(text)

                for f in Path(tmpdir).glob("*.srt"):
                    text = f.read_text(encoding="utf-8")
                    return self._parse_srt(text)

        except Exception as e:
            logger.debug(f"yt-dlp subtitles failed for {video_id}: {e}")
        return ""

    @staticmethod
    def _parse_vtt(text: str) -> str:
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                continue
            if re.match(r"^\d{2}:\d{2}", line):
                continue
            if re.match(r"^\d+$", line):
                continue
            line = re.sub(r"<[^>]+>", "", line)
            line = re.sub(r"\{[^}]+\}", "", line)
            if line and line not in lines[-1:]:
                lines.append(line)
        return " ".join(lines)

    @staticmethod
    def _parse_srt(text: str) -> str:
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or re.match(r"^\d+$", line) or re.match(r"\d{2}:\d{2}", line):
                continue
            line = re.sub(r"<[^>]+>", "", line)
            if line and line not in lines[-1:]:
                lines.append(line)
        return " ".join(lines)
