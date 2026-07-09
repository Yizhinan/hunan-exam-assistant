"""Current events API — 时政大事件."""

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.llm_client import chat_json
from app.core.security import decode_token
from app.models.current_event import CurrentEvent, CATEGORIES, RELEVANCE_LEVELS
from app.api.admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/events",
    tags=["events"],
)


# ============================================================
# Schemas
# ============================================================


class EventOut(BaseModel):
    id: str
    title: str
    description: str
    event_date: str
    category: str
    relevance: str
    source: str | None
    year: int
    created_at: str | None


class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    page_size: int


class RefreshResponse(BaseModel):
    generated: int
    added: int
    skipped: int


# ============================================================
# Endpoints
# ============================================================


@router.get("", response_model=EventListResponse)
async def list_events(
    year: int | None = Query(None, description="年份，默认当前年"),
    category: str | None = Query(None, description="领域分类"),
    relevance: str | None = Query(None, description="考试相关度：必知/了解/拓展"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db = Depends(get_db),
    user_id: str = Depends(decode_token),
):
    """List current events with filtering and pagination."""
    if year is None:
        year = date.today().year

    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"无效的领域分类: {category}")
    if relevance is not None and relevance not in RELEVANCE_LEVELS:
        raise HTTPException(status_code=400, detail=f"无效的相关度: {relevance}")

    query = select(CurrentEvent).where(
        CurrentEvent.is_active == True,
        CurrentEvent.year == year,
    )
    count_query = select(func.count(CurrentEvent.id)).where(
        CurrentEvent.is_active == True,
        CurrentEvent.year == year,
    )

    if category:
        query = query.where(CurrentEvent.category == category)
        count_query = count_query.where(CurrentEvent.category == category)

    if relevance:
        query = query.where(CurrentEvent.relevance == relevance)
        count_query = count_query.where(CurrentEvent.relevance == relevance)

    query = query.order_by(CurrentEvent.event_date.desc())

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    events_result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    events = events_result.scalars().all()

    def _format_dt(dt):
        return dt.isoformat() if dt else None

    return EventListResponse(
        items=[
            EventOut(
                id=e.id,
                title=e.title,
                description=e.description,
                event_date=e.event_date.isoformat() if e.event_date else "",
                category=e.category,
                relevance=e.relevance,
                source=e.source,
                year=e.year,
                created_at=_format_dt(e.created_at),
            )
            for e in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_events(
    year: int | None = Query(None, description="目标年份，默认当前年"),
    _admin = Depends(require_admin),
):
    """Trigger crawler to fetch current events (admin only)."""
    from app.tasks.crawl import crawl_events

    try:
        result = crawl_events.delay()
        return RefreshResponse(
            generated=0, added=0, skipped=0
        )  # async — results come via Celery
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"爬虫任务触发失败：{str(e)}",
        )


# ============================================================
# Ingest schemas
# ============================================================


class IngestEventItem(BaseModel):
    title: str
    content: str
    source_url: str = ""
    source_name: str = ""
    event_date: str = ""


class IngestEventsRequest(BaseModel):
    items: list[IngestEventItem]


class IngestResponse(BaseModel):
    ingested: int
    skipped: int


# LLM classification prompt — only classifies, does NOT generate content
CLASSIFY_PROMPT = """你是一位公务员考试时政辅导专家。请对以下新闻进行考试分类。

领域分类（category）从以下选择：
科技、政治党建、经济、文化、体育、外交、民生、生态

考试相关度（relevance）从以下选择：
- "必知"：涉及国家最高荣誉、重大政策、党代会/全会、国家级表彰
- "了解"：部委级别政策、行业重要事件
- "拓展"：有加分价值的背景素材、地方性事件

只返回 JSON：{"category": "科技", "relevance": "必知"}"""


@router.post("/ingest", response_model=IngestResponse)
async def ingest_events(
    req: IngestEventsRequest,
    db = Depends(get_db),
):
    """Ingest crawled current events — classify with LLM, store to DB."""
    today = date.today()

    # Fetch existing titles for dedup
    existing_result = await db.execute(
        select(CurrentEvent.title, CurrentEvent.year)
    )
    existing = set(existing_result.all())  # {(title, year), ...}

    ingested = 0
    skipped = 0

    for item in req.items:
        title = item.title.strip()
        if not title or len(item.content) < 100:
            skipped += 1
            continue

        # Determine year from event_date or use current year
        try:
            ev_year = date.fromisoformat(item.event_date).year if item.event_date else today.year
        except (ValueError, TypeError):
            ev_year = today.year

        if (title, ev_year) in existing:
            skipped += 1
            continue

        # Classify with LLM
        category = "政治党建"
        relevance = "了解"
        try:
            classification = await asyncio.to_thread(
                chat_json,
                CLASSIFY_PROMPT,
                f"标题：{title}\n\n正文：{item.content[:800]}",
                "deepseek-chat",
                0.1,
                256,
            )
            cat = classification.get("category", "")
            rel = classification.get("relevance", "")
            if cat in CATEGORIES:
                category = cat
            if rel in RELEVANCE_LEVELS:
                relevance = rel
        except Exception as e:
            logger.warning("LLM classification failed for '%s': %s", title[:50], e)
            # Fall through with defaults

        # Description: first 300 chars of content
        desc = item.content[:300].strip()
        if len(item.content) > 300:
            desc += "……"

        # Parse event_date
        try:
            ev_date = date.fromisoformat(item.event_date)
        except (ValueError, TypeError):
            ev_date = today

        event = CurrentEvent(
            title=title,
            description=desc,
            event_date=ev_date,
            category=category,
            relevance=relevance,
            source=item.source_url,
            year=ev_year,
        )
        db.add(event)
        existing.add((title, ev_year))
        ingested += 1

    await db.commit()
    logger.info("Events ingest: %d ingested, %d skipped", ingested, skipped)
    return IngestResponse(ingested=ingested, skipped=skipped)
