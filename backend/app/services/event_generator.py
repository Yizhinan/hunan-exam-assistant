"""LLM-powered current event generator for exam prep."""

import asyncio
import logging
from datetime import date
from typing import Any

from sqlalchemy import select

from app.core.llm_client import chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位湖南省公务员考试时政辅导专家。请生成 {year} 年中国国内发生的重大时政事件列表，这些事件可能成为公务员考试常识判断和申论写作的考点。

核心原则：公务员考试不会只考"某年某月开了什么会"，而是考察具体的人物、成果、数据、政策名称和实质内容。每条事件必须有足够的细节支撑答题。

要求：
1. 覆盖以下领域：科技、政治党建、经济、文化、体育、外交、民生、生态
2. 每个领域选择 3-5 个本年度最具代表性的事件
3. 标注每个事件的考试相关度：
   - "必知"：国家最高级别事件（如国家科技奖、党代会、重大政策出台）
   - "了解"：部委级别或行业重大事件
   - "拓展"：有加分价值的背景素材
4. 每个事件的 description 至少包含 3-5 句话，必须包含以下细节：
   - 具体人名（获奖者、发言人、负责人）
   - 具体成果或数据（奖项名称、项目名称、政策文件名、统计数字）
   - 背景意义（为什么重要、与哪些国家战略相关）
   - 切忌写成"某会议召开"一笔带过——那毫无考试价值

返回 JSON 格式：
{
  "events": [
    {
      "title": "标题需包含核心人物或成果，如：李德仁、薛其坤获2024年度国家最高科学技术奖",
      "description": "详细描述，3-5句话，含具体人名、成果名、数据、背景意义",
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
    prompt = SYSTEM_PROMPT.replace("{year}", str(year))
    try:
        result = await asyncio.to_thread(chat_json, prompt, user_message, "deepseek-chat", 0.2, 16384)
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
