from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from iu.collectors.base import BaseCollector
from iu.models import RawItem

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "InformationUnion/0.1",
}
LOOKBACK_DAYS = 7


class GitHubCollector(BaseCollector):
    source = "github"

    async def collect(self) -> list[RawItem]:
        items = []
        persons = [p for p in self.config.persons if p.github]

        if not persons:
            return items

        cutoff = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)

        async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
            for person in persons:
                try:
                    # Get recent public events
                    events = await self._get_user_events(client, person.github, cutoff)
                    items.extend(events)

                    # Get recently created repos
                    repos = await self._get_recent_repos(client, person.github, cutoff)
                    items.extend(repos)

                    logger.info(f"GitHub [{person.name}]: {len(events)} events, {len(repos)} new repos")
                except Exception as e:
                    logger.warning(f"GitHub [{person.name}] failed: {e}")

        return items

    async def _get_user_events(self, client: httpx.AsyncClient,
                                username: str, cutoff: datetime) -> list[RawItem]:
        """Get recent public events for a user."""
        items = []
        url = f"{GITHUB_API}/users/{username}/events/public"
        resp = await client.get(url, params={"per_page": 30})

        if resp.status_code != 200:
            logger.debug(f"GitHub events for {username}: HTTP {resp.status_code}")
            return items

        for event in resp.json():
            created = event.get("created_at", "")
            if not created:
                continue

            try:
                event_date = datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
                if event_date < cutoff:
                    continue
            except ValueError:
                continue

            event_type = event.get("type", "")
            repo_name = event.get("repo", {}).get("name", "")
            payload = event.get("payload", {})

            title, content = self._format_event(event_type, repo_name, payload)

            if title:
                items.append(RawItem(
                    source="github",
                    source_url=f"https://github.com/{username}",
                    author=username,
                    author_handle=username,
                    title=title,
                    content=content,
                    published_at=event_date.isoformat(),
                    metadata={
                        "event_type": event_type,
                        "repo": repo_name,
                    },
                    person_id=self._get_person_id(username),
                ))

        return items

    async def _get_recent_repos(self, client: httpx.AsyncClient,
                                 username: str, cutoff: datetime) -> list[RawItem]:
        """Get recently created public repos."""
        items = []
        url = f"{GITHUB_API}/users/{username}/repos"
        resp = await client.get(url, params={"sort": "created", "direction": "desc", "per_page": 10})

        if resp.status_code != 200:
            return items

        for repo in resp.json():
            created = repo.get("created_at", "")
            if not created:
                continue

            try:
                repo_date = datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
                if repo_date < cutoff:
                    continue
            except ValueError:
                continue

            desc = repo.get("description", "") or ""
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language", "") or ""

            items.append(RawItem(
                source="github",
                source_url=repo.get("html_url", ""),
                author=username,
                author_handle=username,
                title=f"New repo: {repo.get('name', '')}",
                content=f"{desc}\nLanguage: {lang} | Stars: {stars}",
                published_at=repo_date.isoformat(),
                metadata={
                    "event_type": "new_repo",
                    "repo": repo.get("full_name", ""),
                    "stars": stars,
                    "language": lang,
                },
                person_id=self._get_person_id(username),
            ))

        return items

    def _get_person_id(self, username: str) -> str | None:
        for p in self.config.persons:
            if p.github == username:
                return p.id
        return None

    @staticmethod
    def _format_event(event_type: str, repo: str, payload: dict) -> tuple[str, str]:
        """Format GitHub event into title and content."""
        if event_type == "PushEvent":
            commits = payload.get("commits", [])
            branch = payload.get("ref", "").replace("refs/heads/", "")
            commit_msgs = [c.get("message", "").split("\n")[0] for c in commits[:3]]
            title = f"Push to {repo} ({branch})"
            content = "\n".join(commit_msgs)
            return title, content

        elif event_type == "CreateEvent":
            ref_type = payload.get("ref_type", "")
            ref = payload.get("ref", "")
            if ref_type == "repository":
                return f"Created repo: {repo}", payload.get("description", "")
            return f"Created {ref_type}: {ref} in {repo}", ""

        elif event_type == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            title = f"PR {action}: {pr.get('title', '')} in {repo}"
            content = (pr.get("body", "") or "")[:300]
            return title, content

        elif event_type == "IssuesEvent":
            action = payload.get("action", "")
            issue = payload.get("issue", {})
            title = f"Issue {action}: {issue.get('title', '')} in {repo}"
            content = (issue.get("body", "") or "")[:300]
            return title, content

        elif event_type == "WatchEvent":
            return f"Starred: {repo}", ""

        elif event_type == "ForkEvent":
            return f"Forked: {repo}", ""

        elif event_type == "ReleaseEvent":
            release = payload.get("release", {})
            return f"Release: {release.get('tag_name', '')} in {repo}", (release.get("body", "") or "")[:300]

        elif event_type == "PublicEvent":
            return f"Made public: {repo}", ""

        return "", ""
