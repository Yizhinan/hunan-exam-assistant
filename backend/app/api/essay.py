"""申论批改 API — submit, get result, history."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import decode_token
from app.core.grading_engine import get_grading_engine, GradingResult, DimensionScore
from app.models.essay import EssaySubmission

router = APIRouter(
    prefix="/api/essay",
    tags=["essay"],
    dependencies=[Depends(decode_token)],
)

# ============================================================
# Request / Response schemas
# ============================================================


class GradeRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=5000, description="申论题目")
    material: str = Field(..., min_length=1, max_length=20000, description="给定资料/参考材料")
    answer: str = Field(..., min_length=50, max_length=10000, description="考生作答")
    use_rag: bool = Field(default=True, description="是否启用 RAG 增强批改")


class DimensionResponse(BaseModel):
    key: str
    name: str
    score: float
    weight: float
    comment: str
    highlights: list[str]
    issues: list[str]


class GradingResponse(BaseModel):
    essay_id: str
    total_score: float
    grade: str
    dimensions: list[DimensionResponse]
    overall_comment: str
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    model_revision: str
    hunan_relevance: str
    status: str


class EssayHistoryItem(BaseModel):
    id: str
    question: str
    material: str | None = None
    total_score: float | None
    grade: str | None
    status: str
    created_at: str


class HistoryResponse(BaseModel):
    items: list[EssayHistoryItem]
    total: int
    page: int
    page_size: int


# ============================================================
# Helpers
# ============================================================


def _to_dimension_response(d: DimensionScore) -> DimensionResponse:
    return DimensionResponse(
        key=d.key,
        name=d.name,
        score=d.score,
        weight=d.weight,
        comment=d.comment,
        highlights=d.highlights,
        issues=d.issues,
    )


def _to_grading_response(essay: EssaySubmission) -> GradingResponse:
    result = essay.grading_result or {}
    dims_raw = result.get("dimensions", [])
    return GradingResponse(
        essay_id=str(essay.id),
        total_score=essay.total_score or 0,
        grade=essay.grade or "",
        dimensions=[_to_dimension_response(DimensionScore(**d)) for d in dims_raw],
        overall_comment=result.get("overall_comment", ""),
        strengths=result.get("strengths", []),
        weaknesses=result.get("weaknesses", []),
        suggestions=result.get("suggestions", []),
        model_revision=result.get("model_revision", ""),
        hunan_relevance=result.get("hunan_relevance", ""),
        status=essay.status,
    )


# ============================================================
# Endpoints
# ============================================================


@router.post("/grade", response_model=GradingResponse, status_code=status.HTTP_201_CREATED)
async def grade_essay(
    req: GradeRequest,
    user_id: str = Depends(decode_token),
    db = Depends(get_db),
):
    """提交申论作答进行 AI 批改"""
    essay = EssaySubmission(
        user_id=user_id,
        question=req.question,
        material=req.material or None,
        answer=req.answer,
        word_count=len(req.answer),
        status="grading",
    )
    db.add(essay)
    await db.commit()
    await db.refresh(essay)

    try:
        engine = get_grading_engine()
        result: GradingResult = engine.grade(
            question=req.question,
            answer=req.answer,
            material=req.material or "",
            use_rag=req.use_rag,
        )

        essay.total_score = result.total_score
        essay.grade = result.grade
        essay.grading_result = {
            "dimensions": [
                {
                    "key": d.key,
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "comment": d.comment,
                    "highlights": d.highlights,
                    "issues": d.issues,
                }
                for d in result.dimensions
            ],
            "overall_comment": result.overall_comment,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "suggestions": result.suggestions,
            "model_revision": result.model_revision,
            "hunan_relevance": result.hunan_relevance,
        }
        essay.status = "completed"
        await db.commit()
        await db.refresh(essay)

        return _to_grading_response(essay)

    except Exception as e:
        essay.status = "error"
        essay.error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批改失败: {str(e)}",
        )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user_id: str = Depends(decode_token),
    db = Depends(get_db),
):
    """获取当前用户的批改历史"""
    total_result = await db.execute(
        select(func.count(EssaySubmission.id)).where(
            EssaySubmission.user_id == user_id
        )
    )
    total = total_result.scalar() or 0

    query = (
        select(EssaySubmission)
        .where(EssaySubmission.user_id == user_id)
        .order_by(EssaySubmission.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    essays_result = await db.execute(query)
    essays = essays_result.scalars().all()

    return HistoryResponse(
        items=[
            EssayHistoryItem(
                id=str(e.id),
                question=e.question[:100] + "..." if len(e.question) > 100 else e.question,
                material=e.material[:100] + "..." if e.material and len(e.material) > 100 else e.material,
                total_score=e.total_score,
                grade=e.grade,
                status=e.status,
                created_at=e.created_at.isoformat(),
            )
            for e in essays
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{essay_id}", response_model=GradingResponse)
async def get_essay_result(
    essay_id: str,
    user_id: str = Depends(decode_token),
    db = Depends(get_db),
):
    """获取单篇批改详情"""
    essay_result = await db.execute(
        select(EssaySubmission).where(
            EssaySubmission.id == essay_id,
            EssaySubmission.user_id == user_id,
        )
    )
    essay = essay_result.scalar_one_or_none()

    if essay is None:
        raise HTTPException(status_code=404, detail="批改记录不存在")
    if essay.status not in ("completed",):
        raise HTTPException(status_code=400, detail="批改尚未完成")

    return _to_grading_response(essay)
