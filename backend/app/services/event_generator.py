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
1. 覆盖以下领域，每个领域选择 3-5 个本年度最具代表性的事件：
   - 科技：国家科技奖、重大科技突破、航天成就、院士评选等
   - 政治党建：七一勋章/八一勋章/国家荣誉称号颁授、党代会/全会、重要纪念日讲话、主题教育、反腐大案、重要人事任免等
   - 经济：GDP数据、重大政策（如民营经济促进法）、自贸区、重要协议签署等
   - 文化：世界遗产、考古发现、重要文化奖项等
   - 体育：奥运会/亚运会/全运会成绩、重要赛事等
   - 外交：主场外交、重要出访、国际组织任职等
   - 民生：医保/养老/教育重大改革、自然灾害及救援等
   - 生态：双碳目标进展、国家公园、环保督察等

2. 标注每个事件的考试相关度：
   - "必知"：国家最高级别事件（如七一勋章颁授、国家科技奖、党代会、重大政策出台）
   - "了解"：部委级别或行业重大事件
   - "拓展"：有加分价值的背景素材

3. 每个事件的 description 至少 3-5 句话，必须包含：
   - 具体人名（获奖者、发言人、负责人）——这是最重要的考点！
   - 具体成果或数据（奖项名称、项目名称、政策文件名、统计数字）
   - 背景意义（为什么重要、与哪些国家战略相关）
   - 切忌写成"某会议召开"一笔带过——那毫无考试价值

4. 特别注意：
   - 七一勋章、八一勋章、国家荣誉称号、时代楷模、感动中国等人物的姓名和事迹必须详细列出
   - 如你无法确定某事件的具体细节（受训练数据限制），宁可标注来源也不可编造虚假信息
   - 如果 {year} 年尚未结束，请基于已发生的事实生成，不确定的日期标注大致月份即可

返回 JSON 格式：
{
  "events": [
    {
      "title": "标题需包含核心人物，如：XX等N人获颁七一勋章 / 李德仁、薛其坤获国家最高科学技术奖",
      "description": "详细描述，至少3-5句话，含具体人名、奖项名、事迹、数据、政策背景",
      "event_date": "YYYY-MM-DD",
      "category": "政治党建",
      "relevance": "必知",
      "source": "新华社/人民日报/央视新闻"
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

    today_str = date.today().isoformat()
    user_message = (
        f"请生成 {year} 年中国重大时政事件列表。"
        f"今天是 {today_str}，请尽量生成 {year}年1月1日 至 {today_str} 之间的事件。"
        f"事件日期不要晚于 {today_str}。"
    )
    prompt = SYSTEM_PROMPT.replace("{year}", str(year))
    try:
        result = await asyncio.to_thread(chat_json, prompt, user_message, "deepseek-v4-pro", 0.2, 16384)
        logger.info("LLM raw response keys: %s, events count: %d", list(result.keys()), len(result.get("events", [])))
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

    today = date.today()
    added = 0
    skipped = 0
    future_rejected = 0
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

        # Reject events with future dates (LLM hallucination guard)
        if event_date > today:
            future_rejected += 1
            continue

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
        "Event generation complete: generated=%d added=%d skipped=%d future_rejected=%d",
        len(events), added, skipped, future_rejected,
    )
    return {"generated": len(events), "added": added, "skipped": skipped}
