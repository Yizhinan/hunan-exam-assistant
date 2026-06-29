"""Celery tasks for automated crawling — 定时爬取真题和时政."""

import subprocess
import sys
from pathlib import Path

from app.tasks.celery_app import celery_app

# Path to the Scrapy project relative to the backend directory
CRAWLER_DIR = Path(__file__).resolve().parent.parent.parent.parent / "crawler"


def _run_spider(spider_name: str) -> dict:
    """Run a Scrapy spider and return result summary."""
    result = subprocess.run(
        [sys.executable, "-m", "scrapy", "crawl", spider_name],
        cwd=str(CRAWLER_DIR),
        capture_output=True,
        text=True,
        timeout=600,  # 10 min timeout
    )
    return {
        "spider": spider_name,
        "returncode": result.returncode,
        "stdout_lines": len(result.stdout.splitlines()),
        "stderr": result.stderr[-500:] if result.stderr else "",
    }


@celery_app.task(name="app.tasks.crawl.crawl_news")
def crawl_news():
    """
    Daily task: crawl Hunan current affairs news.

    Runs these spiders:
      - hunan_gov: 湖南省政府政务动态
      - rednet: 红网湖南频道
    """
    results = {}
    for spider in ["hunan_gov", "rednet"]:
        try:
            results[spider] = _run_spider(spider)
        except Exception as e:
            results[spider] = {"error": str(e)}

    return results


@celery_app.task(name="app.tasks.crawl.crawl_exams")
def crawl_exams():
    """
    Weekly task: check for new Hunan exam questions.

    Runs these spiders:
      - offcn_exam: 中公教育湖南真题
      - huatu_exam: 华图教育真题
    """
    results = {}
    for spider in ["offcn_exam", "huatu_exam"]:
        try:
            results[spider] = _run_spider(spider)
        except Exception as e:
            results[spider] = {"error": str(e)}

    return results


@celery_app.task(name="app.tasks.crawl.crawl_all")
def crawl_all():
    """Run all crawlers (manual trigger)."""
    news_result = crawl_news()
    exam_result = crawl_exams()
    return {"news": news_result, "exams": exam_result}
