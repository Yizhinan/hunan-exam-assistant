"""
考情分析 API — 基于真实职位表和面试成绩数据

核心逻辑：
  1. 硬条件过滤：学历/学位/性别/年龄/经历/专业
  2. 意向筛选：城市 + 岗位类别
  3. 按进面分从低到高排序（容易进面的优先）
  4. 进面分来自面试名单真实数据
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.difficulty import compute_batch_difficulties
from app.core.security import decode_token
from app.models.position import PositionHistory, UserProfile

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# ============================================================
class ProfileRequest(BaseModel):
    birth_year: int | None = Field(None, ge=1960, le=2010)
    gender: str | None = Field(None)
    education: str | None = Field(None)
    degree: str | None = Field(None)
    major: str | None = Field(None)
    political_status: str | None = Field(None)
    work_experience_years: int | None = Field(None, ge=0, le=40)
    preferred_cities: str | None = Field(None)
    preferred_category: str | None = Field(None)
    year: int = Field(2026, ge=2023, le=2026)

class PositionOut(BaseModel):
    id: str; year: int; city: str; city_label: str; district: str | None
    department: str; position_name: str; exam_category: str
    education_requirement: str; degree_requirement: str
    major_requirement: str | None; political_requirement: str
    gender_requirement: str; experience_requirement: str; age_limit: str
    enrollment_count: int; applicant_count: int | None
    competition_ratio: float | None
    min_score_interview: float | None; max_score_interview: float | None
    avg_score_interview: float | None; interview_ratio: str
    match_score: int; match_details: list[str]; risk_level: str
    predicted_score: float | None
    difficulty_score: float  # 0-100, 越低越容易
    difficulty_breakdown: dict  # {admission_score, competition_ratio, enrollment_scale, trend_adjustment, total}
    tier: str  # 保底 / 稳妥 / 冲刺

class AnalysisResult(BaseModel):
    profile: ProfileRequest; total_positions: int; matched_positions: int
    recommendations: list[PositionOut]; summary: str

# ============================================================
EDU_LEVEL = {"大专": 1, "本科": 2, "大学本科": 2, "硕士研究生": 3, "研究生": 3, "博士研究生": 4}
DEG_LEVEL = {"无要求": 0, "无": 0, "学士": 1, "硕士": 2, "博士": 3}

MAJOR_MAP = {
    "法学": ["法学","法律","法学类","法学大类","公安学类","公安学","监狱学","侦查学"],
    "会计": ["会计","会计学","财务管理","审计","财务会计类"],
    "计算机": ["计算机","软件","网络","电子信息","计算机类","信息与计算"],
    "中文": ["中文","汉语言","文秘","中国语言文学","新闻传播","新闻"],
    "经济": ["经济","金融","财政","贸易","经济学类"],
    "管理": ["管理","公共管理","工商管理","行政管理","公共事业"],
    "土木": ["土木","建筑","工程管理","城乡规划","建筑学"],
    "医学": ["医学","临床","药学","护理","基础医学"],
}


def major_match(user_major: str | None, req_major: str | None) -> bool:
    if not req_major or req_major == "不限": return True
    if not user_major: return True  # 没填专业则所有专业不限的都能过
    u = user_major.strip().replace("类", "")
    r = req_major.strip().replace("，", ",")
    # 直接匹配
    if u in r or r in u: return True
    # 大类匹配
    for cat, kws in MAJOR_MAP.items():
        u_in = any(k in u for k in kws)
        r_in = any(k in r for k in kws)
        if u_in and r_in: return True
    # 逐一匹配
    for part in r.split(","):
        p = part.strip().replace("类", "")
        if p and (p in u or u in p): return True
    # 如果岗位要求了具体专业但用户专业不匹配 → false
    return False


def city_match(pos: PositionHistory, cities: list[str]) -> bool:
    for c in cities:
        if pos.city == c: return True
        if pos.district and c in pos.district: return True
    return False


# ============================================================
@router.post("/recommend", response_model=AnalysisResult)
async def recommend_positions(
    req: ProfileRequest,
    user_id: str = Depends(decode_token),
    db: Session = Depends(get_db),
):
    # Save profile
    existing = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    if existing:
        for k, v in req.model_dump(exclude_none=True).items():
            if k != "year": setattr(existing, k, v)
    else:
        db.add(UserProfile(user_id=user_id, **{k:v for k,v in req.model_dump(exclude_none=True).items() if k!="year"}))
    db.commit()

    # Load all positions for the year
    all_pos = db.execute(select(PositionHistory).where(
        PositionHistory.year == req.year, PositionHistory.is_active == True
    )).scalars().all()
    total = len(all_pos)

    # User attributes
    user_edu = EDU_LEVEL.get(req.education or "", 2)
    user_deg = DEG_LEVEL.get(req.degree or "", 1)
    user_age = 2026 - (req.birth_year or 2000)
    cities = [c.strip() for c in (req.preferred_cities or "").split(",") if c.strip()]
    cat = req.preferred_category

    matched = []
    for pos in all_pos:
        details = []; score = 50

        # === 硬条件 ===
        # 学历
        req_edu = 2
        for k, v in EDU_LEVEL.items():
            if k in pos.education_requirement: req_edu = v; break
        if user_edu < req_edu: continue
        score += 10 if user_edu > req_edu else 5

        # 学位 (如果有要求)
        req_deg = 0
        for k, v in DEG_LEVEL.items():
            if k in pos.degree_requirement: req_deg = v; break
        if req_deg > 0 and user_deg < req_deg: continue

        # 性别
        if pos.gender_requirement not in ("不限", ""):
            if req.gender and req.gender != pos.gender_requirement: continue
            score += 3; details.append(f"性别: {pos.gender_requirement}")

        # 年龄
        max_age = 35
        if "30" in pos.age_limit: max_age = 30
        elif "25" in pos.age_limit: max_age = 25
        if user_age > max_age: continue
        if max_age <= 30: details.append(f"年龄: ≤{pos.age_limit}")

        # 基层经历
        if pos.experience_requirement not in ("不限", ""):
            if (req.work_experience_years or 0) < 2: continue
            score += 5

        # 专业
        if not major_match(req.major, pos.major_requirement): continue
        if req.major and pos.major_requirement and pos.major_requirement != "不限":
            score += 5; details.append(f"专业: {req.major}")

        # 学历/学位详细信息
        details.append(f"学历: ≥{pos.education_requirement}")

        matched.append((pos, score, details))

    # === 三级严格筛选 ===
    # Level 1: 城市 AND 类别同时匹配
    level1 = []
    for pos, score, details in matched:
        city_ok = not cities or city_match(pos, cities)
        cat_ok = not cat or pos.exam_category == cat
        if city_ok and cat_ok:
            bonus = 0
            new_d = list(details)
            lbl = pos.city_label
            if pos.city == "省直" and pos.district:
                lbl = f"省直(驻{pos.district})"
            if cities: new_d.append(f"✅ 城市: {lbl}")
            if cat: new_d.append(f"✅ 类别: {pos.exam_category}")
            if pos.min_score_interview is not None:
                bonus += 10
                new_d.append("✅ 有进面数据")
            level1.append((pos, min(100, score+bonus), new_d))

    # Check if level1 has any scored positions
    level1_scored = [item for item in level1 if item[0].min_score_interview is not None]

    if level1 and level1_scored:
        # 有精确匹配且有分数 → 只用 level1
        ranked = level1
        filter_msg = "精确匹配"
    elif level1 and not level1_scored and cities and "省直" not in cities:
        # 用户选了非省直城市，但该城市无分数 → 自动补省直
        level1_plus = list(level1)
        for pos, score, details in matched:
            if pos.city == "省直" and (not cat or pos.exam_category == cat):
                bonus = 10
                new_d = list(details)
                lbl = pos.city_label
                if pos.district: lbl = f"省直(驻{pos.district})"
                new_d.append(f"📌 省直岗位: {lbl}")
                new_d.append(f"✅ 类别: {pos.exam_category}")
                level1_plus.append((pos, min(100, score+bonus+5), new_d))
        ranked = level1_plus
        filter_msg = "您选的城市暂无进面数据，已自动补充省直岗位"
    elif level1 or (not cities and not cat):
        # 有精确匹配 → 只用 level1
        ranked = level1
        filter_msg = "精确匹配"
    else:
        # Level 2: 城市 OR 类别匹配（降级）
        level2 = []
        for pos, score, details in matched:
            city_ok = not cities or city_match(pos, cities)
            cat_ok = not cat or pos.exam_category == cat
            if city_ok or cat_ok:
                bonus = 0
                new_d = list(details)
                if city_ok and cities: new_d.append(f"⚠️ 城市: {pos.city_label}")
                if cat_ok and cat: new_d.append(f"⚠️ 类别: {pos.exam_category}")
                level2.append((pos, min(100, score+5), new_d))
        if level2:
            ranked = level2
            filter_msg = "未找到同时满足城市和类别的岗位，已放宽"
        else:
            ranked = [(pos, score, list(details)) for pos, score, details in matched]
            filter_msg = "未找到匹配岗位，显示全部"

    # === 难度评分与排序 ===
    candidate_positions = [item[0] for item in ranked]
    difficulty_map = {}
    if candidate_positions:
        diff_results = compute_batch_difficulties(candidate_positions)
        difficulty_map = {p.id: b for p, b in diff_results}
        # Re-sort ranked by difficulty total (lower = easier)
        def diff_sort_key(item):
            pos, score, details = item
            d = difficulty_map.get(pos.id)
            return d.total if d else 50.0
        ranked.sort(key=diff_sort_key)

    # === 构建结果 ===
    recommendations = []
    for pos, score, details in ranked[:20]:
        ms = pos.min_score_interview
        predicted = round(ms * 2, 1) if ms and ms < 100 else (ms or None)
        risk = "高" if (predicted or 0) > 140 else "中" if (predicted or 0) > 130 else "低"

        d = difficulty_map.get(pos.id)
        if d:
            diff_score = d.total
            diff_breakdown = {
                "admission_score": d.admission_score,
                "competition_ratio": d.competition_ratio,
                "enrollment_scale": d.enrollment_scale,
                "trend_adjustment": d.trend_adjustment,
                "total": d.total,
            }
            tier = d.tier
        else:
            diff_score = 50.0
            diff_breakdown = {}
            tier = "稳妥"

        lbl = pos.city_label
        if pos.city == "省直" and pos.district: lbl = f"省直(驻{pos.district})"

        recommendations.append(PositionOut(
            id=str(pos.id), year=pos.year, city=pos.city, city_label=lbl,
            district=pos.district, department=pos.department,
            position_name=pos.position_name, exam_category=pos.exam_category,
            education_requirement=pos.education_requirement,
            degree_requirement=pos.degree_requirement,
            major_requirement=pos.major_requirement,
            political_requirement=pos.political_requirement,
            gender_requirement=pos.gender_requirement,
            experience_requirement=pos.experience_requirement,
            age_limit=pos.age_limit,
            enrollment_count=pos.enrollment_count,
            applicant_count=pos.applicant_count,
            competition_ratio=pos.competition_ratio,
            min_score_interview=ms, max_score_interview=pos.max_score_interview,
            avg_score_interview=pos.avg_score_interview,
            interview_ratio=pos.interview_ratio,
            match_score=score, match_details=details,
            risk_level=risk, predicted_score=predicted,
            difficulty_score=diff_score,
            difficulty_breakdown=diff_breakdown,
            tier=tier,
        ))

    n_scored = sum(1 for p,_,_ in ranked[:20] if p.min_score_interview is not None)
    summary = (
        f"{req.year}年湖南省考共{total}个岗位，符合条件{len(matched)}个。"
        f"推荐{len(ranked[:20])}个（{filter_msg}）。"
        f"按上岸难度从低到高排列。"
    )

    return AnalysisResult(
        profile=req, total_positions=total, matched_positions=len(matched),
        recommendations=recommendations, summary=summary,
    )


@router.get("/profile")
async def get_profile(user_id: str = Depends(decode_token), db: Session = Depends(get_db)):
    p = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    if not p: return {"exists": False}
    return {"exists": True, "birth_year": p.birth_year, "gender": p.gender,
            "education": p.education, "degree": p.degree, "major": p.major,
            "political_status": p.political_status,
            "work_experience_years": p.work_experience_years,
            "preferred_cities": p.preferred_cities, "preferred_category": p.preferred_category}

@router.get("/cities")
async def list_cities(year: int = Query(2026), db: Session = Depends(get_db)):
    result = db.execute(select(PositionHistory.city, func.count(PositionHistory.id))
        .where(PositionHistory.is_active == True, PositionHistory.year == year)
        .group_by(PositionHistory.city).order_by(PositionHistory.city)).all()
    labels = {"省直":"省直机关","长沙":"长沙市","株洲":"株洲市","湘潭":"湘潭市","衡阳":"衡阳市",
              "邵阳":"邵阳市","岳阳":"岳阳市","常德":"常德市","张家界":"张家界市","益阳":"益阳市",
              "郴州":"郴州市","永州":"永州市","怀化":"怀化市","娄底":"娄底市","湘西":"湘西州"}
    return [{"code":r[0],"label":labels.get(r[0],r[0]),"count":r[1]} for r in result]

@router.get("/years")
async def list_years(db: Session = Depends(get_db)):
    result = db.execute(select(PositionHistory.year, func.count(PositionHistory.id))
        .where(PositionHistory.is_active == True)
        .group_by(PositionHistory.year).order_by(PositionHistory.year.desc())).all()
    return [{"year":r[0],"count":r[1]} for r in result]
