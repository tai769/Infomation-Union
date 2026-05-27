from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    source: str
    source_url: str
    author: str = ""
    author_handle: str = ""
    title: str = ""
    content: str = ""
    published_at: str = ""
    media_urls: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    person_id: str | None = None
    product_id: str | None = None

    @property
    def id(self) -> str:
        return str(uuid.uuid4())

    @property
    def collected_at(self) -> str:
        return datetime.utcnow().isoformat()


@dataclass
class Person:
    id: str
    name: str
    twitter: str = ""
    youtube: str = ""
    reddit: str = ""
    tags: list[str] = field(default_factory=list)
    active: bool = True


@dataclass
class Product:
    id: str
    name: str
    company: str = ""
    tags: list[str] = field(default_factory=list)
    active: bool = True


@dataclass
class Analysis:
    id: str = ""
    item_id: str = ""
    created_at: str = ""
    method: str = ""
    model: str = ""
    summary: str = ""
    positive: str = ""
    negative: str = ""
    probability: dict = field(default_factory=dict)
    cross_validation: str = ""
    raw_response: str = ""


@dataclass
class Report:
    id: str = ""
    week_start: str = ""
    week_end: str = ""
    created_at: str = ""
    summary: str = ""
    item_ids: list[str] = field(default_factory=list)
    analysis_ids: list[str] = field(default_factory=list)
    delivered_email: bool = False
    delivered_at: str = ""
