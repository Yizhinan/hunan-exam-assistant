"""Current events API — 时政大事件."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import decode_token
from app.models.current_event import CurrentEvent
from app.api.admin import require_admin

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
    db = Depends(get_db),
    _admin = Depends(require_admin),
):
    """Trigger LLM generation of current events (admin only)."""
    from app.services.event_generator import generate_events

    try:
        result = await generate_events(db, year)
        return RefreshResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"事件生成失败：{str(e)}",
        )
