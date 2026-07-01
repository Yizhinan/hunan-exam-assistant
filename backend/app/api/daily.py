"""每日范文 API — today's picks (by category), archive, topics, manual refresh."""

import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.core.security import decode_token
from app.models.daily_essay import DailyEssay, EXAM_CATEGORIES

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/daily",
    tags=["daily"],
    dependencies=[Depends(decode_token)],
)

# ============================================================
# Schemas
# ============================================================


class DailyEssayOut(BaseModel):
    id: str
    title: str
    content: str
    topic: str | None
    source_name: str | None
    source_url: str | None
    exam_category: str
    recommend_date: str
    highlights: str | None
    key_points: str | None
    view_count: int


class DailyEssayListItem(BaseModel):
    id: str
    title: str
    topic: str | None
    source_name: str | None
    exam_category: str
    recommend_date: str
    highlights: str | None


class DailyListResponse(BaseModel):
    items: list[DailyEssayListItem]
    total: int


class TodayResponse(BaseModel):
    date: str
    essays: list[DailyEssayOut]
    categories_available: list[str]


class CategoryInfo(BaseModel):
    category: str
    count: int
    label: str


# ============================================================
# Endpoints
# ============================================================


@router.get("/today", response_model=TodayResponse)
async def get_today_essays(
    category: str | None = Query(None, description="按岗位类别筛选"),
    db = Depends(get_db),
):
    """
    获取今日推荐范文。
    若不指定 category，返回今日所有类别（行政执法/县乡基层/省市直）各一篇。
    """
    today = date.today()

    query = select(DailyEssay).where(
        DailyEssay.recommend_date == today,
        DailyEssay.is_active == True,
    )

    if category:
        query = query.where(DailyEssay.exam_category == category)

    query = query.order_by(DailyEssay.exam_category)
    essays_result = await db.execute(query)
    essays = essays_result.scalars().all()

    if not essays:
        # Fallback: most recent day with essays
        latest_result = await db.execute(
            select(DailyEssay.recommend_date)
            .where(DailyEssay.is_active == True)
            .order_by(desc(DailyEssay.recommend_date))
            .limit(1)
        )
        latest_date_result = latest_result.scalar_one_or_none()

        if latest_date_result is None:
            raise HTTPException(status_code=404, detail="暂无范文，请先添加范文数据")

        query = select(DailyEssay).where(
            DailyEssay.recommend_date == latest_date_result,
            DailyEssay.is_active == True,
        )
        if category:
            query = query.where(DailyEssay.exam_category == category)
        essays_fb_result = await db.execute(query.order_by(DailyEssay.exam_category))
        essays = essays_fb_result.scalars().all()
        today = latest_date_result

    # Increment view counts
    for e in essays:
        e.view_count += 1
    await db.commit()

    # Collect available categories for today
    all_today = [e.exam_category for e in essays]
    if not category:
        all_today = [e.exam_category for e in essays]

    return TodayResponse(
        date=today.isoformat(),
        essays=[
            DailyEssayOut(
                id=str(e.id),
                title=e.title,
                content=e.content,
                topic=e.topic,
                source_name=e.source_name,
                source_url=e.source_url,
                exam_category=e.exam_category,
                recommend_date=e.recommend_date.isoformat(),
                highlights=e.highlights,
                key_points=e.key_points,
                view_count=e.view_count,
            )
            for e in essays
        ],
        categories_available=list(dict.fromkeys(all_today)),
    )


@router.get("/archive", response_model=DailyListResponse)
async def list_daily_essays(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    topic: str | None = Query(None),
    category: str | None = Query(None, description="按岗位类别筛选: 行政执法/县乡基层/省市直"),
    db = Depends(get_db),
):
    """获取历史范文列表（分页 + 主题筛选 + 类别筛选）。"""
    query = select(DailyEssay).where(DailyEssay.is_active == True)
    count_query = select(func.count(DailyEssay.id)).where(DailyEssay.is_active == True)

    if topic:
        query = query.where(DailyEssay.topic == topic)
        count_query = count_query.where(DailyEssay.topic == topic)
    if category:
        query = query.where(DailyEssay.exam_category == category)
        count_query = count_query.where(DailyEssay.exam_category == category)

    query = query.order_by(desc(DailyEssay.recommend_date), DailyEssay.exam_category)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    essays_result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    essays = essays_result.scalars().all()

    return DailyListResponse(
        items=[
            DailyEssayListItem(
                id=str(e.id),
                title=e.title,
                topic=e.topic,
                source_name=e.source_name,
                exam_category=e.exam_category,
                recommend_date=e.recommend_date.isoformat(),
                highlights=e.highlights[:200] + "..." if e.highlights and len(e.highlights) > 200 else e.highlights,
            )
            for e in essays
        ],
        total=total,
    )


@router.get("/topics")
async def list_topics(db = Depends(get_db)):
    """获取所有范文主题标签."""
    topics_result = await db.execute(
        select(DailyEssay.topic, func.count(DailyEssay.id))
        .where(DailyEssay.is_active == True, DailyEssay.topic.isnot(None))
        .group_by(DailyEssay.topic)
        .order_by(desc(func.count(DailyEssay.id)))
    )
    result = topics_result.all()

    return [{"topic": row[0], "count": row[1]} for row in result]


@router.get("/categories")
async def list_categories(db = Depends(get_db)):
    """获取岗位类别及其范文数量。"""
    cat_result = await db.execute(
        select(DailyEssay.exam_category, func.count(DailyEssay.id))
        .where(DailyEssay.is_active == True)
        .group_by(DailyEssay.exam_category)
        .order_by(DailyEssay.exam_category)
    )
    result = cat_result.all()

    # Build ordered list with labels
    label_map = {
        "行政执法": "行政执法岗",
        "县乡基层": "县乡基层岗",
        "省市直": "省市直岗",
        "综合通用": "综合通用",
    }
    return [
        {"category": row[0], "count": row[1], "label": label_map.get(row[0], row[0])}
        for row in result
    ]


class RefreshResponse(BaseModel):
    started: bool = True
    message: str = ""


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_daily_essays(
    use_ai: bool = Query(default=True, description="是否用 AI 分析范文亮点"),
    count: int = Query(default=1, ge=1, le=10, description="抓取篇数（1-10）"),
):
    """
    手动刷新范文 — 后台从互联网抓取真实申论范文 + LLM 智能提取正文 + AI 分析。

    接口立即返回，实际抓取在后台异步执行（约 10-30 秒/篇）。
    刷新完成后前端重新请求 /api/daily/today 即可看到新范文。
    """
    try:
        from scripts.fetch_daily_essays import refresh_essays_async

        # Fire-and-forget: run in background, return immediately
        async def _bg_refresh():
            try:
                result = await refresh_essays_async(use_ai=use_ai, count=count)
                logger.info(
                    "后台刷新完成: status=%s scraped=%s imported=%s analyzed=%s errors=%s",
                    result["status"], result["total_scraped"],
                    result["imported"], result["analyzed"], len(result.get("errors", [])),
                )
            except Exception as e:
                logger.exception("后台刷新失败: %s", e)

        asyncio.create_task(_bg_refresh())

        return RefreshResponse(
            started=True,
            message=f"开始从互联网抓取最新申论范文（{count}篇），约需10-30秒，请稍后刷新页面查看",
        )
    except Exception as e:
        logger.exception("Failed to start daily essay refresh")
        raise HTTPException(status_code=500, detail=f"刷新范文失败: {e}")


@router.get("/{essay_id}", response_model=DailyEssayOut)
async def get_daily_essay_detail(essay_id: str, db = Depends(get_db)):
    """获取单篇范文详情。"""
    essay_result = await db.execute(
        select(DailyEssay).where(DailyEssay.id == essay_id)
    )
    essay = essay_result.scalar_one_or_none()

    if essay is None:
        raise HTTPException(status_code=404, detail="范文不存在")

    essay.view_count += 1
    await db.commit()

    return DailyEssayOut(
        id=str(essay.id),
        title=essay.title,
        content=essay.content,
        topic=essay.topic,
        source_name=essay.source_name,
        source_url=essay.source_url,
        exam_category=essay.exam_category,
        recommend_date=essay.recommend_date.isoformat(),
        highlights=essay.highlights,
        key_points=essay.key_points,
        view_count=essay.view_count,
    )
