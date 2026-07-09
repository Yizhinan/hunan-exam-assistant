"""Celery application configuration."""

from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hunan_exam",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.grading", "app.tasks.crawl", "app.tasks.events"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "crawl-news-daily": {
            "task": "app.tasks.crawl.crawl_news",
            "schedule": 86400.0,  # daily
        },
        "crawl-exams-weekly": {
            "task": "app.tasks.crawl.crawl_exams",
            "schedule": 604800.0,  # weekly
        },
        "crawl-essays-weekly": {
            "task": "app.tasks.crawl.crawl_essays",
            "schedule": 604800.0,  # weekly
        },
        "generate-events-weekly": {
            "task": "app.tasks.events.generate_events",
            "schedule": 604800.0,  # weekly
        },
    },
)
