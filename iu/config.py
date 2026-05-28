from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class PersonConfig(BaseModel):
    id: str
    name: str
    twitter: str = ""
    youtube_channel: str = ""
    reddit: str = ""
    github: str = ""
    tags: list[str] = Field(default_factory=list)


class ProductConfig(BaseModel):
    id: str
    name: str
    company: str = ""
    tags: list[str] = Field(default_factory=list)


class TwitterConfig(BaseModel):
    enabled: bool = True
    nitter_instances: list[str] = Field(default_factory=lambda: [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
    ])


class YouTubeConfig(BaseModel):
    enabled: bool = True
    api_key: str = ""


class RedditConfig(BaseModel):
    enabled: bool = True
    subreddits: list[str] = Field(default_factory=lambda: [
        "MachineLearning",
        "artificial",
        "LocalLLaMA",
        "ChatGPT",
        "ClaudeAI",
    ])


class RSSFeedConfig(BaseModel):
    url: str
    name: str = ""


class RSSConfig(BaseModel):
    enabled: bool = True
    feeds: list[RSSFeedConfig] = Field(default_factory=lambda: [
        RSSFeedConfig(url="https://openai.com/blog/rss.xml", name="OpenAI Blog"),
        RSSFeedConfig(url="https://www.anthropic.com/feed.xml", name="Anthropic Blog"),
        RSSFeedConfig(url="https://hnrss.org/newest?q=AI+agent", name="HN AI"),
    ])


class NewsConfig(BaseModel):
    enabled: bool = True
    newsapi_key: str = ""


class AnalysisConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "MiMo-V2.5-Pro"
    max_tokens: int = 4096
    batch_size: int = 20


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = Field(default_factory=list)


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class GitHubConfig(BaseModel):
    enabled: bool = True
    token: str = ""  # Optional: increases rate limit from 60 to 5000 req/hour


class NewsletterFeedConfig(BaseModel):
    url: str
    name: str = ""
    author: str = ""


class NewsletterConfig(BaseModel):
    enabled: bool = True
    feeds: list[NewsletterFeedConfig] = Field(default_factory=list)


class AppConfig(BaseModel):
    persons: list[PersonConfig] = Field(default_factory=list)
    products: list[ProductConfig] = Field(default_factory=list)
    twitter: TwitterConfig = Field(default_factory=TwitterConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    rss: RSSConfig = Field(default_factory=RSSConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    newsletter: NewsletterConfig = Field(default_factory=NewsletterConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    web: WebConfig = Field(default_factory=WebConfig)


def load_config(path: Path | None = None) -> AppConfig:
    p = path or CONFIG_PATH
    if not p.exists():
        return AppConfig()
    with open(p) as f:
        data = yaml.safe_load(f) or {}
    return AppConfig(**data)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    p = path or CONFIG_PATH
    with open(p, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True, sort_keys=False)
