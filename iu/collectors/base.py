from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod

from iu.config import AppConfig
from iu.db import (
    get_active_persons, get_active_products,
    item_exists, insert_item, add_mention, compute_hash,
)
from iu.models import RawItem

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    source: str = ""

    def __init__(self, config: AppConfig, conn):
        self.config = config
        self.conn = conn

    @abstractmethod
    async def collect(self) -> list[RawItem]:
        """Fetch new items from this source."""
        ...

    async def run(self) -> int:
        """Collect, dedup, insert, link mentions. Returns count of new items."""
        items = await self.collect()
        new_count = 0

        persons = get_active_persons(self.conn)
        products = get_active_products(self.conn)

        for item in items:
            h = compute_hash(item.source, item.source_url)
            if item_exists(self.conn, h):
                continue

            item_id = item.id
            insert_item(
                self.conn,
                item_id=item_id,
                source=item.source,
                source_url=item.source_url,
                content_hash=h,
                author=item.author,
                author_handle=item.author_handle,
                title=item.title,
                content=item.content,
                published_at=item.published_at,
                collected_at=item.collected_at,
                media_urls=item.media_urls,
                metadata=item.metadata,
                person_id=item.person_id,
                product_id=item.product_id,
            )

            # Link mentions
            self._link_mentions(item_id, item, persons, products)
            new_count += 1

        self.conn.commit()
        return new_count

    def _link_mentions(self, item_id: str, item: RawItem,
                       persons: list[dict], products: list[dict]) -> None:
        text = f"{item.title} {item.content}".lower()
        if not text.strip():
            return

        for person in persons:
            name = person["name"].lower()
            twitter = (person.get("twitter") or "").lower()
            if name and name in text:
                add_mention(self.conn, item_id, "person", person["id"])
            elif twitter and f"@{twitter}" in text:
                add_mention(self.conn, item_id, "person", person["id"])

        for product in products:
            name = product["name"].lower()
            if name and name in text:
                add_mention(self.conn, item_id, "product", product["id"])
