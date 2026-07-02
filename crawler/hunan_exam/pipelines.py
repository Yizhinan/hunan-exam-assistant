"""Scrapy pipelines: dedup, store via backend API."""

import hashlib
import logging

import httpx
from scrapy.exceptions import DropItem

from hunan_exam.items import ExamQuestionItem, NewsArticleItem, EssayItem

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
    POST scraped items to the backend /api/knowledge/ingest endpoint.

    Items are batched for efficiency. The batch is flushed when full or
    when the spider closes.
    """

    BATCH_SIZE = 50
    API_TIMEOUT = 120.0  # seconds — ingestion can be slow
    MAX_RETRIES = 3

    def open_spider(self, spider):
        self.buffer: list[dict] = []
        self.api_base = spider.settings.get(
            "BACKEND_API_BASE", "http://localhost:8000"
        )
        self.api_token = spider.settings.get("BACKEND_API_TOKEN", "")
        spider.logger.info(
            f"Pipeline API target: {self.api_base}/api/knowledge/ingest"
        )

    def process_item(self, item, spider):
        """Convert item to ingest payload dict and buffer."""
        payload = self._item_to_payload(item, spider)
        if payload is None:
            return item  # Unknown item type, pass through

        self.buffer.append(payload)
        if len(self.buffer) >= self.BATCH_SIZE:
            self._flush(spider)
        return item

    def close_spider(self, spider):
        """Flush remaining items on spider close."""
        if self.buffer:
            self._flush(spider)

    # -------- private helpers --------

    def _item_to_payload(self, item, spider) -> dict | None:
        """Map Scrapy Item to the /api/knowledge/ingest item schema."""
        if isinstance(item, ExamQuestionItem):
            text = item.get("question_text", "")
            if item.get("answer_text"):
                text += "\n\n【参考答案】\n" + item["answer_text"]
            if item.get("analysis_text"):
                text += "\n\n【解析】\n" + item["analysis_text"]
            return {
                "doc_type": "exam",
                "title": (item.get("question_text", "") or "无标题")[:200],
                "content": text,
                "source_url": item.get("source_url", ""),
                "source_name": item.get("source_name", ""),
                "exam_year": item.get("exam_year"),
            }

        elif isinstance(item, NewsArticleItem):
            return {
                "doc_type": "news",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "source_url": item.get("source_url", ""),
                "source_name": item.get("source_name", ""),
                "category": item.get("category", ""),
                "tags": item.get("tags", []),
            }

        elif isinstance(item, EssayItem):
            return {
                "doc_type": "model",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "source_url": item.get("source_url", ""),
                "source_name": item.get("source_name", ""),
                "topic": item.get("topic", ""),
            }

        else:
            spider.logger.warning(f"Unknown item type: {type(item)}")
            return None

    def _flush(self, spider):
        """POST buffered items to the backend."""
        batch = self.buffer[:]
        self.buffer.clear()

        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        url = f"{self.api_base}/api/knowledge/ingest"

        for attempt in range(self.MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.API_TIMEOUT) as client:
                    response = client.post(
                        url,
                        json={"items": batch},
                        headers=headers,
                    )
                if response.status_code == 200:
                    data = response.json()
                    spider.logger.info(
                        f"Ingested {data.get('ingested', 0)}/{len(batch)} items "
                        f"(skipped: {data.get('skipped', 0)}, errors: {data.get('errors', 0)})"
                    )
                    for r in data.get("results", []):
                        if r.get("status") == "error":
                            spider.logger.error(
                                f"Item [{r['index']}] '{r['title']}': {r.get('error')}"
                            )
                    return
                elif response.status_code == 401:
                    spider.logger.error(
                        "Pipeline auth failed — check BACKEND_API_TOKEN"
                    )
                    return  # Don't retry auth failures
                else:
                    spider.logger.warning(
                        f"Ingest attempt {attempt + 1} failed: HTTP {response.status_code}"
                    )
            except Exception as e:
                spider.logger.warning(
                    f"Ingest attempt {attempt + 1} failed: {e}"
                )

        # All retries exhausted
        spider.logger.error(
            f"Ingest FAILED after {self.MAX_RETRIES} attempts. "
            f"Dropped {len(batch)} items: {[i['title'] for i in batch]}"
        )
