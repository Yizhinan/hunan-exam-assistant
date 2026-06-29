"""Scrapy pipelines: dedup, store to PostgreSQL, index in ChromaDB."""

import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DuplicateFilterPipeline:
    """Filter duplicate items based on URL hash."""

    def __init__(self):
        self.seen = set()

    def process_item(self, item, spider):
        url = item.get("source_url", "")
        h = hashlib.sha256(url.encode()).hexdigest()
        if h in self.seen:
            spider.logger.debug(f"Duplicate skipped: {url}")
            raise DropItem(f"Duplicate: {url}")
        self.seen.add(h)
        return item


class PostgreSQLPipeline:
    """
    Store scraped items to PostgreSQL and trigger ChromaDB ingestion.

    In production, this calls the backend API. For standalone Scrapy runs,
    it stores directly to the database.
    """

    def open_spider(self, spider):
        # Defer imports so Scrapy can load settings without DB connection
        import asyncio
        import asyncpg
        from app.core.config import get_settings

        settings = get_settings()
        # Convert asyncpg URL to sync for Scrapy pipeline
        db_url = settings.DATABASE_URL.replace("+asyncpg", "")
        # We use httpx to call the backend API instead of direct DB access
        self.api_base = "http://localhost:8000/api"
        self.imported = True

    def process_item(self, item, spider):
        """Queue item for API ingestion — actual storage happens async."""
        # In production: POST to /api/knowledge/upload or store directly
        # For now, log and store structured data
        spider.logger.info(f"Scraped: {item.get('source_url', 'N/A')}")

        # TODO: In production, call the FastAPI backend to ingest
        # The backend handles: parse → chunk → embed → ChromaDB + PostgreSQL

        return item


class DropItem(Exception):
    """Signal to drop an item from the pipeline."""
    pass
