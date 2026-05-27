from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)


class YouTubeCollector(BaseCollector):
    source = "youtube"

    async def collect(self) -> list[RawItem]:
        items = []
        persons = [p for p in self.config.persons if p.youtube_channel]

        if not persons:
            return items

        api_key = self.config.youtube.api_key

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            for person in persons:
                try:
                    video_ids = await self._get_recent_videos(client, person.youtube_channel, api_key)
                    for vid in video_ids[:10]:  # Max 10 per channel
                        subtitle_text = self._extract_subtitles(vid)
                        if subtitle_text:
                            items.append(RawItem(
                                source="youtube",
                                source_url=f"https://www.youtube.com/watch?v={vid}",
                                author=person.name,
                                author_handle=person.youtube_channel,
                                title=f"YouTube video by {person.name}",
                                content=subtitle_text[:5000],  # Limit subtitle length
                                published_at=datetime.utcnow().isoformat(),
                                metadata={"video_id": vid},
                                person_id=person.id,
                            ))
                    logger.info(f"YouTube [{person.name}]: {len(video_ids)} videos found")
                except Exception as e:
                    logger.warning(f"YouTube [{person.name}] failed: {e}")

        return items

    async def _get_recent_videos(self, client: httpx.AsyncClient,
                                  channel_id: str, api_key: str) -> list[str]:
        """Get recent video IDs from a channel."""
        if api_key:
            return await self._get_videos_via_api(client, channel_id, api_key)
        return await self._get_videos_via_scrape(client, channel_id)

    async def _get_videos_via_api(self, client: httpx.AsyncClient,
                                   channel_id: str, api_key: str) -> list[str]:
        """Use YouTube Data API v3."""
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "key": api_key,
            "channelId": channel_id,
            "part": "snippet",
            "order": "date",
            "maxResults": 10,
            "type": "video",
        }
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return [item["id"]["videoId"] for item in data.get("items", [])]

    async def _get_videos_via_scrape(self, client: httpx.AsyncClient,
                                      channel_id: str) -> list[str]:
        """Scrape channel page for video IDs (fallback)."""
        url = f"https://www.youtube.com/channel/{channel_id}/videos"
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        ids = re.findall(r'"videoId":"([^"]+)"', resp.text)
        return list(dict.fromkeys(ids))[:10]  # Dedup, limit 10

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

                # Find subtitle file
                for f in Path(tmpdir).glob("*.vtt"):
                    text = f.read_text(encoding="utf-8")
                    return self._parse_vtt(text)

                # Try .srt
                for f in Path(tmpdir).glob("*.srt"):
                    text = f.read_text(encoding="utf-8")
                    return self._parse_srt(text)

        except Exception as e:
            logger.debug(f"yt-dlp failed for {video_id}: {e}")
        return ""

    @staticmethod
    def _parse_vtt(text: str) -> str:
        """Parse VTT subtitle to plain text."""
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                continue
            if re.match(r"^\d{2}:\d{2}", line):
                continue
            if re.match(r"^\d+$", line):
                continue
            # Remove VTT tags
            line = re.sub(r"<[^>]+>", "", line)
            line = re.sub(r"\{[^}]+\}", "", line)
            if line and line not in lines[-1:]:
                lines.append(line)
        return " ".join(lines)

    @staticmethod
    def _parse_srt(text: str) -> str:
        """Parse SRT subtitle to plain text."""
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or re.match(r"^\d+$", line) or re.match(r"\d{2}:\d{2}", line):
                continue
            line = re.sub(r"<[^>]+>", "", line)
            if line and line not in lines[-1:]:
                lines.append(line)
        return " ".join(lines)
