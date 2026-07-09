"""LLM-powered current event generator for exam prep."""

import asyncio
import logging
from datetime import date
from typing import Any

from sqlalchemy import select

from app.core.llm_client import chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位湖南省公务员考试时政辅导专家。请生成 {year} 年中国国内发生的重大时政事件列表，这些事件可能成为公务员考试常识判断的考点。

要求：
1. 覆盖以下领域：科技、政治党建、经济、文化、体育、外交、民生、生态
2. 每个领域选择 3-5 个本年度最具代表性的事件
3. 标注每个事件的考试相关度：
   - "必知"：国家最高级别事件（如国家科技奖、党代会、重大政策出台）
   - "了解"：部委级别或行业重大事件
   - "拓展"：有加分价值的背景素材
4. 每个事件提供 2-3 句话的简洁描述

返回 JSON 格式：
{
  "events": [
    {
      "title": "事件标题",
      "description": "2-3句话描述",
      "event_date": "YYYY-MM-DD",
      "category": "科技",
      "relevance": "必知",
      "source": "新华社"
    }
  ]
}"""


async def generate_events(db: Any, year: int | None = None) -> dict:
    """Generate current events for a given year via DeepSeek LLM.

    Skips events whose titles already exist in the database for that year.

    Args:
        db: database session
        year: target year, defaults to current year

    Returns:
        dict with generated (total from LLM), added (newly inserted), skipped counts
    """
    from app.models.current_event import CurrentEvent

    if year is None:
        year = date.today().year

    user_message = f"请生成 {year} 年中国重大时政事件列表。"
    try:
        result = await asyncio.to_thread(chat_json, SYSTEM_PROMPT.format(year=year), user_message)
        events = result.get("events", [])
    except Exception as e:
        logger.error("LLM event generation failed for year %s: %s", year, e)
        return {"generated": 0, "added": 0, "skipped": 0}

    if not events:
        logger.warning("LLM returned 0 events for year %s", year)
        return {"generated": 0, "added": 0, "skipped": 0}

    # Dedup: fetch existing titles for this year
    existing_result = await db.execute(
        select(CurrentEvent.title).where(CurrentEvent.year == year)
    )
    existing_titles = set(existing_result.scalars().all())

    added = 0
    skipped = 0
    for ev in events:
        title = ev.get("title", "").strip()
        if not title:
            continue
        if title in existing_titles:
            skipped += 1
            continue

        try:
            event_date = date.fromisoformat(ev.get("event_date", f"{year}-01-01"))
        except (ValueError, TypeError):
            event_date = date(year, 1, 1)

        event = CurrentEvent(
            title=title,
            description=ev.get("description", ""),
            event_date=event_date,
            category=ev.get("category", "综合"),
            relevance=ev.get("relevance", "了解"),
            source=ev.get("source", ""),
            year=year,
        )
        db.add(event)
        existing_titles.add(title)
        added += 1

    await db.commit()

    logger.info(
        "Event generation complete: generated=%d added=%d skipped=%d",
        len(events), added, skipped,
    )
    return {"generated": len(events), "added": added, "skipped": skipped}
