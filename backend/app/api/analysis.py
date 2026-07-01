"""
考情分析 API — 基于真实职位表和面试成绩数据

核心逻辑：
  1. 硬条件过滤：学历/学位/性别/年龄/经历/专业
  2. 意向筛选：城市 + 岗位类别
  3. 按进面分从低到高排序（容易进面的优先）
  4. 进面分来自面试名单真实数据
  5. 难度分预计算缓存 + 响应缓存（5min TTL）
"""

import hashlib
import json
import time
import threading
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.difficulty_cache import get_cache
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
    preferred_category: str | None = Field(None)  # 现在匹配 org_category（组织系统类别）
    preferred_essay_category: str | None = Field(None)  # 申论类别：省市卷 / 县乡卷 / 行政执法卷
    exclude_professional_subject: bool = False  # 排除加试专业科目的岗位（公安/财经/法律等）
    year: int = Field(2026, ge=2023, le=2026)

class PositionOut(BaseModel):
    id: str; year: int; city: str; city_label: str; district: str | None
    department: str; position_name: str; exam_category: str
    org_category: str | None  # 组织系统类别（Excel sheet 名）
    education_requirement: str; degree_requirement: str
    major_requirement: str | None; political_requirement: str
    gender_requirement: str; experience_requirement: str; age_limit: str
    exam_subject: str | None  # 笔试科目（行测+申论，可能含加试）
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


# ============================================================
# 省直岗位：从部门名称提取实际所在城市
# 湖南省XX监狱、湖南省XX强制隔离戒毒所 → 城市名
_PROVINCIAL_DEPT_CITY_MAP: dict[str, str] = {
    # 地级市名（直接出现在部门名中）
    "长沙": "长沙", "株洲": "株洲", "湘潭": "湘潭", "衡阳": "衡阳",
    "邵阳": "邵阳", "岳阳": "岳阳", "常德": "常德", "张家界": "张家界",
    "益阳": "益阳", "郴州": "郴州", "永州": "永州", "怀化": "怀化",
    "娄底": "娄底", "湘西": "湘西",
    # 县级市/地名 → 所属地级市
    "津市": "常德", "茶陵": "株洲", "网岭": "株洲", "攸县": "株洲",
    "雁北": "衡阳", "雁南": "衡阳", "衡南": "衡阳", "耒阳": "衡阳", "常宁": "衡阳",
    "赤山": "益阳", "沅江": "益阳", "南县": "益阳", "安化": "益阳",
    "德山": "常德", "武陵": "常德", "桃源": "常德", "石门": "常德", "临澧": "常德",
    "东安": "永州", "祁阳": "永州", "道县": "永州", "宁远": "永州",
    "星城": "长沙", "长康": "长沙", "坪塘": "长沙",
    "麓山": "长沙", "黎托": "长沙", "新开铺": "长沙",
    "涟源": "娄底", "冷水江": "娄底", "新化": "娄底",
    "汨罗": "岳阳", "临湘": "岳阳", "华容": "岳阳", "平江": "岳阳", "湘阴": "岳阳",
    "醴陵": "株洲", "韶山": "湘潭", "湘乡": "湘潭",
    "武冈": "邵阳", "邵东": "邵阳", "隆回": "邵阳", "洞口": "邵阳",
    "慈利": "张家界", "桑植": "张家界",
    "沅陵": "怀化", "辰溪": "怀化", "溆浦": "怀化", "会同": "怀化",
    "桂阳": "郴州", "宜章": "郴州", "永兴": "郴州", "嘉禾": "郴州",
    "龙山": "湘西", "永顺": "湘西", "凤凰": "湘西", "花垣": "湘西",
    "保靖": "湘西", "古丈": "湘西", "泸溪": "湘西",
    "蓝山": "永州", "江华": "永州", "新田": "永州", "双牌": "永州",
    "芷江": "怀化", "麻阳": "怀化", "新晃": "怀化", "靖州": "怀化", "通道": "怀化",
    # 特殊机构（默认在长沙）
    "女子": "长沙", "未成年": "长沙",
    # 补充：监狱/戒毒所的历史地名
    "潭州": "长沙",    # 潭州=长沙古称，湖南省潭州监狱在长沙
    "湘南": "衡阳",    # 湘南监狱在衡阳地区
}

# Sort by key length descending for longest-match-first
_PROVINCIAL_DEPT_CITY_KEYS = sorted(_PROVINCIAL_DEPT_CITY_MAP.keys(), key=lambda k: -len(k))


def _extract_city_from_dept(dept_name: str) -> str | None:
    """Try to extract the prefecture city from an 省直 department name.

    湖南省岳阳监狱 → 岳阳
    湖南省津市监狱 → 常德 (津市属于常德)
    湖南省女子监狱 → None (无法推断)
    """
    for loc in _PROVINCIAL_DEPT_CITY_KEYS:
        if loc in dept_name:
            return _PROVINCIAL_DEPT_CITY_MAP[loc]
    return None


def city_match(pos: PositionHistory, cities: list[str]) -> bool:
    for c in cities:
        # 1) 城市直接匹配
        if pos.city == c:
            return True
        # 2) 区县名包含目标城市
        if pos.district and c in pos.district:
            return True
        # 3) 省直岗位：尝试从部门名提取实际城市
        if pos.city == "省直":
            inferred = _extract_city_from_dept(pos.department)
            if inferred and inferred == c:
                return True
            # 如果district有值（如"长沙市"），且包含目标城市
            if pos.district and c in pos.district:
                return True
            # 无法定位的纯省级机关（如湖南省教育厅）只在未筛选城市时出现
    return False


def detect_essay_category(exam_subject: str | None) -> str | None:
    """从 exam_subject 提取申论卷类型（省市卷 / 县乡卷 / 行政执法卷）。"""
    if not exam_subject:
        return None
    s = exam_subject.strip()
    if "行政执法卷" in s:
        return "行政执法卷"
    if "省市卷" in s:
        return "省市卷"
    if "县乡卷" in s:
        return "县乡卷"
    return None


# ============================================================
# ============================================================
# Response cache (simple TTL-based in-memory cache)
_response_cache: dict[str, tuple[float, dict]] = {}
_response_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes


def _cache_key(req: ProfileRequest, user_id: str) -> str:
    """Generate a deterministic cache key from request params."""
    raw = json.dumps(req.model_dump(exclude_none=True), sort_keys=True) + user_id
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    with _response_cache_lock:
        entry = _response_cache.get(key)
        if entry and time.time() - entry[0] < _CACHE_TTL:
            return entry[1]
        if entry:
            del _response_cache[key]
    return None


def _cache_set(key: str, data: dict):
    with _response_cache_lock:
        _response_cache[key] = (time.time(), data)
        # Prune expired entries if cache grows too large
        if len(_response_cache) > 200:
            now = time.time()
            expired = [k for k, v in _response_cache.items() if now - v[0] > _CACHE_TTL]
            for k in expired:
                del _response_cache[k]


@router.post("/recommend", response_model=AnalysisResult)
async def recommend_positions(
    req: ProfileRequest,
    user_id: str = Depends(decode_token),
    db = Depends(get_db),
):
    # --- Response cache check ---
    ck = _cache_key(req, user_id)
    cached = _cache_get(ck)
    if cached:
        return cached

    # --- Lazy-init difficulty cache (all years, so cross-year trend works) ---
    await get_cache().ensure_init(db)

    # Save profile
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in req.model_dump(exclude_none=True).items():
            if k not in ("year", "exclude_professional_subject"): setattr(existing, k, v)
    else:
        db.add(UserProfile(user_id=user_id, **{k:v for k,v in req.model_dump(exclude_none=True).items() if k not in ("year","exclude_professional_subject")}))
    await db.commit()

    # Load all positions for the year
    all_pos_result = await db.execute(select(PositionHistory).where(
        PositionHistory.year == req.year, PositionHistory.is_active == True
    ))
    all_pos = all_pos_result.scalars().all()
    total = len(all_pos)

    # User attributes
    user_edu = EDU_LEVEL.get(req.education or "", 2)
    user_deg = DEG_LEVEL.get(req.degree or "", 1)
    user_age = 2026 - (req.birth_year or 2000)
    cities = [c.strip() for c in (req.preferred_cities or "").split(",") if c.strip()]
    org_cat = req.preferred_category  # now matches org_category (组织系统类别)
    essay_cat = req.preferred_essay_category  # 申论卷类别

    # Number of filter dimensions the user has set
    n_filters_set = sum([bool(cities), bool(org_cat), bool(essay_cat)])

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

        # 排除需加试专业科目的岗位（公安/财经/法律等）
        # 考试科目格式：行测、申论（X卷） 或 行测、申论（X卷）、XX专业知识
        # 注意：部分岗位 exam_subject 为 NULL（如公安局岗位），需同时检查 department
        _PROFESSIONAL_KEYWORDS = ["公安", "专业知识", "专业科目"]
        if req.exclude_professional_subject:
            if pos.exam_subject and any(kw in pos.exam_subject for kw in _PROFESSIONAL_KEYWORDS):
                continue
            # exam_subject 为空时不漏掉公安系统的岗位
            if pos.department and "公安" in pos.department:
                continue

        # 学历/学位详细信息
        details.append(f"学历: ≥{pos.education_requirement}")

        # === 软条件：三维度匹配计数 ===
        city_ok = not cities or city_match(pos, cities)
        org_ok = not org_cat or pos.org_category == org_cat
        pos_essay = detect_essay_category(pos.exam_subject)
        essay_ok = not essay_cat or pos_essay == essay_cat

        # n_matched: only count dimensions where the user actually set a filter
        n_matched = sum([
            bool(cities) and city_ok,
            bool(org_cat) and org_ok,
            bool(essay_cat) and essay_ok,
        ])
        matched.append((pos, score, details, city_ok, org_ok, essay_ok, n_matched))

    # === 三级智能筛选 ===
    MIN_RECOMMENDATIONS = 8  # 最少推荐数，精确匹配不足时自动放宽补充

    # Level 1: 所有已设筛选维度全部匹配 (exact match)
    level1 = []
    for pos, score, details, city_ok, org_ok, essay_ok, n_matched in matched:
        if n_filters_set == 0 or n_matched == n_filters_set:
            bonus = 0
            new_d = list(details)
            lbl = pos.city_label
            if pos.city == "省直" and pos.district:
                lbl = f"省直(驻{pos.district})"
            if cities: new_d.append(f"✅ 城市: {lbl}")
            if org_cat: new_d.append(f"✅ 组织类别: {pos.org_category or '未知'}")
            if essay_cat:
                pos_essay = detect_essay_category(pos.exam_subject)
                new_d.append(f"✅ 申论类别: {pos_essay or '未知'}")
            if pos.min_score_interview is not None:
                bonus += 10
                new_d.append("✅ 有进面数据")
            level1.append((pos, min(100, score+bonus), new_d))

    # Level 2: 放宽匹配 — 至少 n_filters_set-1 个维度匹配（最多差 1 个）
    level1_ids = {item[0].id for item in level1}
    level2 = []
    for pos, score, details, city_ok, org_ok, essay_ok, n_matched in matched:
        if pos.id in level1_ids:
            continue
        # Level 2 triggers when at least 2 filters are set and we match n_set-1 of them
        if n_filters_set >= 2 and n_matched == n_filters_set - 1:
            bonus = 0
            new_d = list(details)
            if city_ok and cities: new_d.append(f"⚠️ 城市: {pos.city_label}")
            elif cities: new_d.append(f"❌ 城市: {pos.city_label}")
            if org_ok and org_cat: new_d.append(f"⚠️ 组织类别: {pos.org_category or '未知'}")
            elif org_cat: new_d.append(f"❌ 组织类别: {pos.org_category or '未知'}")
            if essay_ok and essay_cat:
                pos_essay = detect_essay_category(pos.exam_subject)
                new_d.append(f"⚠️ 申论类别: {pos_essay or '未知'}")
            elif essay_cat:
                pos_essay = detect_essay_category(pos.exam_subject)
                new_d.append(f"❌ 申论类别: {pos_essay or '未知'}")
            level2.append((pos, min(100, score+5), new_d))

    # Check if level1 has any scored positions
    level1_scored = [item for item in level1 if item[0].min_score_interview is not None]

    if level1 and level1_scored and len(level1) >= MIN_RECOMMENDATIONS:
        # 精确匹配足够多 → 只用 level1
        ranked = level1
        filter_msg = "精确匹配"
    elif level1 and len(level1) < MIN_RECOMMENDATIONS:
        # 精确匹配不足 → 用放宽匹配补充（精确匹配排前面）
        ranked = level1 + level2
        if level2:
            filter_msg = f"精确匹配仅{len(level1)}个岗位，已补充{len(level2)}个放宽匹配"
        else:
            filter_msg = "精确匹配"
    elif level1 and not level1_scored and cities and "省直" not in cities:
        # 用户选了非省直城市，但该城市无进面数据 → 自动补省直
        level1_plus = list(level1)
        for pos, score, details, city_ok, org_ok, essay_ok, n_matched in matched:
            if pos.city == "省直" and org_ok and essay_ok:
                bonus = 10
                new_d = list(details)
                lbl = pos.city_label
                if pos.district: lbl = f"省直(驻{pos.district})"
                new_d.append(f"📌 省直岗位: {lbl}")
                if org_cat: new_d.append(f"✅ 组织类别: {pos.org_category or '未知'}")
                if essay_cat: new_d.append(f"✅ 申论类别: {pos_essay or '未知'}")
                level1_plus.append((pos, min(100, score+bonus+5), new_d))
        ranked = level1_plus
        filter_msg = "您选的城市暂无进面数据，已自动补充省直岗位"
    elif level1 or (not cities and not org_cat and not essay_cat):
        # 未设筛选条件 → 全部匹配即 level1
        ranked = level1
        filter_msg = "精确匹配"
    else:
        # 无精确匹配 → 用 level2 或全部岗位
        if level2:
            ranked = level2
            filter_msg = "未找到同时满足城市、组织类别和申论类别的岗位，已放宽"
        else:
            ranked = [(pos, score, list(details)) for pos, score, details, *_ in matched]
            filter_msg = "未找到匹配岗位，显示全部"

    # === 难度评分（从预计算缓存读取） ===
    diff_cache = get_cache()

    # Build trend map (lightweight, keep in real-time)
    trend_map = {}
    candidate_positions = [item[0] for item in ranked]
    if candidate_positions:
        from collections import defaultdict
        by_key = defaultdict(list)
        for p in all_pos:
            if p.min_score_interview is not None:
                by_key[(p.city, p.department)].append((p.year, p.min_score_interview))

        for pos in candidate_positions:
            key = (pos.city, pos.department)
            records = by_key.get(key, [])
            if len(records) >= 2:
                records.sort(key=lambda x: x[0])
                deltas = [records[i+1][1] - records[i][1] for i in range(len(records)-1)]
                avg_delta = sum(deltas) / len(deltas)
                trend_map[pos.id] = max(-10.0, min(10.0, avg_delta))

    # Compound sort: difficulty score (primary) blended with match_score (tiebreaker).
    # Positions with higher match (more criteria matched) get a slight boost so
    # "三不限" positions (lower match, more competitive) don't dominate results.
    # Positions WITH interview scores get a bonus so they surface first.
    def compound_sort_key(item):
        pos, score, _ = item
        d = diff_cache.get(pos.id)
        diff = d["score"] if d else 50.0
        # Each match_score point above baseline 50 reduces effective difficulty by 0.15.
        match_bonus = max(0, score - 50) * 0.15
        # Positions with real interview data get pushed forward (bonus = -5)
        score_bonus = -5.0 if pos.min_score_interview is not None else 0
        return diff - match_bonus + score_bonus
    ranked.sort(key=compound_sort_key)

    # === 构建结果 ===
    recommendations = []
    for pos, score, details in ranked[:20]:
        ms = pos.min_score_interview
        predicted = round(ms * 2, 1) if ms and ms < 100 else (ms or None)
        risk = "高" if (predicted or 0) > 140 else "中" if (predicted or 0) > 130 else "低"

        d = diff_cache.get(pos.id)
        if d:
            diff_score = d["score"]
            diff_breakdown = d["breakdown"]
            tier = d["tier"]
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
            org_category=pos.org_category,
            education_requirement=pos.education_requirement,
            degree_requirement=pos.degree_requirement,
            major_requirement=pos.major_requirement,
            political_requirement=pos.political_requirement,
            gender_requirement=pos.gender_requirement,
            experience_requirement=pos.experience_requirement,
            age_limit=pos.age_limit,
            exam_subject=pos.exam_subject,
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

    # Count positions with real difficulty scores
    n_scored = sum(1 for pos, _, _ in ranked[:20] if diff_cache.get(pos.id) is not None)

    summary = (
        f"{req.year}年湖南省考共{total}个岗位，符合条件{len(matched)}个。"
        f"推荐{len(ranked[:20])}个（{filter_msg}）。"
        f"其中{n_scored}个已完成难度评分，按上岸难度从低到高排列。"
    )

    result = AnalysisResult(
        profile=req, total_positions=total, matched_positions=len(matched),
        recommendations=recommendations, summary=summary,
    )
    _cache_set(ck, result.model_dump())
    return result


@router.get("/profile")
async def get_profile(user_id: str = Depends(decode_token), db = Depends(get_db)):
    p_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    p = p_result.scalar_one_or_none()
    if not p: return {"exists": False}
    return {"exists": True, "birth_year": p.birth_year, "gender": p.gender,
            "education": p.education, "degree": p.degree, "major": p.major,
            "political_status": p.political_status,
            "work_experience_years": p.work_experience_years,
            "preferred_cities": p.preferred_cities, "preferred_category": p.preferred_category,
            "preferred_essay_category": p.preferred_essay_category}

@router.get("/cities")
async def list_cities(year: int = Query(2026), db = Depends(get_db)):
    cities_result = await db.execute(select(PositionHistory.city, func.count(PositionHistory.id))
        .where(PositionHistory.is_active == True, PositionHistory.year == year)
        .group_by(PositionHistory.city).order_by(PositionHistory.city))
    result = cities_result.all()
    labels = {"省直":"省直机关","长沙":"长沙市","株洲":"株洲市","湘潭":"湘潭市","衡阳":"衡阳市",
              "邵阳":"邵阳市","岳阳":"岳阳市","常德":"常德市","张家界":"张家界市","益阳":"益阳市",
              "郴州":"郴州市","永州":"永州市","怀化":"怀化市","娄底":"娄底市","湘西":"湘西州"}
    return [{"code":r[0],"label":labels.get(r[0],r[0]),"count":r[1]} for r in result]

@router.get("/years")
async def list_years(db = Depends(get_db)):
    years_result = await db.execute(select(PositionHistory.year, func.count(PositionHistory.id))
        .where(PositionHistory.is_active == True)
        .group_by(PositionHistory.year).order_by(PositionHistory.year.desc()))
    result = years_result.all()
    return [{"year":r[0],"count":r[1]} for r in result]


@router.get("/trend/{city}")
async def get_city_trend(
    city: str,
    category: str | None = Query(None),
    db = Depends(get_db),
):
    """Get historical score trend for a city, optionally filtered by exam category."""
    query = select(
        PositionHistory.year,
        func.avg(PositionHistory.min_score_interview),
        func.count(PositionHistory.id),
    ).where(
        PositionHistory.city == city,
        PositionHistory.is_active == True,
        PositionHistory.min_score_interview.isnot(None),
    )
    if category:
        query = query.where(PositionHistory.exam_category == category)

    query = query.group_by(PositionHistory.year).order_by(PositionHistory.year)

    rows_result = await db.execute(query)
    rows = rows_result.all()
    data = [
        {"year": row[0], "avg_score": round(float(row[1]), 1), "count": row[2]}
        for row in rows
    ]

    return {"city": city, "category": category, "data": data}


@router.get("/stats/overview")
async def get_stats_overview(db = Depends(get_db)):
    """Get aggregate statistics for all positions."""
    # By city
    city_rows_result = await db.execute(
        select(
            PositionHistory.city,
            func.avg(PositionHistory.min_score_interview),
            func.count(PositionHistory.id),
        ).where(
            PositionHistory.is_active == True,
            PositionHistory.min_score_interview.isnot(None),
        ).group_by(PositionHistory.city).order_by(PositionHistory.city)
    )
    city_rows = city_rows_result.all()

    by_city = [
        {"city": row[0], "avg_score": round(float(row[1]), 1), "count": row[2]}
        for row in city_rows
    ]

    # By category
    cat_rows_result = await db.execute(
        select(
            PositionHistory.exam_category,
            func.avg(PositionHistory.min_score_interview),
            func.count(PositionHistory.id),
        ).where(
            PositionHistory.is_active == True,
            PositionHistory.min_score_interview.isnot(None),
        ).group_by(PositionHistory.exam_category).order_by(PositionHistory.exam_category)
    )
    cat_rows = cat_rows_result.all()

    by_category = [
        {"category": row[0], "avg_score": round(float(row[1]), 1), "count": row[2]}
        for row in cat_rows
    ]

    # Easiest city and category
    easiest_city = min(by_city, key=lambda x: x["avg_score"])["city"] if by_city else ""
    easiest_category = min(by_category, key=lambda x: x["avg_score"])["category"] if by_category else ""

    return {
        "by_city": by_city,
        "by_category": by_category,
        "easiest_city": easiest_city,
        "easiest_category": easiest_category,
    }


@router.post("/cache/refresh")
async def refresh_difficulty_cache(db = Depends(get_db)):
    """Force recompute all difficulty scores. Call after data import."""
    cache = get_cache()
    ok = await cache.refresh(db)
    # Also clear response cache
    with _response_cache_lock:
        _response_cache.clear()
    return {"ok": ok, "size": cache.size, "initialized": cache.initialized}


@router.get("/cache/stats")
async def cache_stats():
    """Get cache status."""
    cache = get_cache()
    with _response_cache_lock:
        resp_entries = len(_response_cache)
    return {
        "difficulty_cache_size": cache.size,
        "difficulty_cache_initialized": cache.initialized,
        "response_cache_entries": resp_entries,
        "response_cache_ttl": _CACHE_TTL,
    }


# ============================================================
# Data Import Endpoints
# ============================================================

class ImportResultResponse(BaseModel):
    success: bool = True
    total_rows: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    not_found: int = 0
    errors: list[dict] = []


def _validate_excel_file(file: UploadFile):
    """Validate uploaded file is .xlsx format."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("xlsx", "xlsm"):
        raise HTTPException(status_code=400, detail=f"仅支持 .xlsx 格式，收到: .{ext}")


@router.post("/import/positions", response_model=ImportResultResponse)
async def import_positions(
    file: UploadFile = File(...),
    year: int = Form(..., ge=2000, le=2030, description="招录年份"),
    db=Depends(get_db),
):
    """
    导入岗位 Excel（支持多 sheet）。

    Excel 表头需包含：考区、单位名称、单位层级、职位名称、职位性质、
    笔试考试科目、招录人数、报考人员身份要求、基层工作年限要求、性别要求、
    最高年龄要求、最低学历要求、学位要求、专业要求 等 23 列。

    去重逻辑：同一 (单位名称, 职位名称, 年份) 视为同一岗位，后导入的覆盖前者。
    """
    _validate_excel_file(file)

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    from app.services.excel_parser import parse_position_excel, import_positions_to_db

    try:
        rows = parse_position_excel(file_bytes, year)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 Excel 失败: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="未从 Excel 中解析到有效岗位数据，请检查表头是否正确")

    result = await import_positions_to_db(db, rows, year)
    return ImportResultResponse(
        success=len(result["errors"]) < len(rows),
        total_rows=result["total_rows"],
        created=result["created"],
        updated=result["updated"],
        skipped=result["skipped"],
        errors=result["errors"],
    )


@router.post("/import/scores", response_model=ImportResultResponse)
async def import_scores(
    file: UploadFile = File(...),
    year: int = Form(..., ge=2000, le=2030, description="招录年份"),
    db=Depends(get_db),
):
    """
    导入进面成绩 Excel。

    Excel 表头需包含：序号、姓名、准考证号、单位名称、职位名称、
    行政职业能力测验成绩、申论成绩、专业成绩、笔试综合成绩、笔试排名。

    按 (单位名称, 职位名称) 分组聚合进面最低分/最高分/平均分，
    匹配 position_history 表中对应岗位并更新分数。
    """
    _validate_excel_file(file)

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    from app.services.score_aggregator import (
        parse_score_excel,
        aggregate_scores,
        import_scores_to_db,
    )

    try:
        score_rows = parse_score_excel(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 Excel 失败: {e}")

    if not score_rows:
        raise HTTPException(status_code=400, detail="未从 Excel 中解析到有效成绩数据，请检查表头是否正确")

    aggregated = aggregate_scores(score_rows)
    result = await import_scores_to_db(db, aggregated, year)

    return ImportResultResponse(
        success=result["not_found"] < result["total_groups"],
        total_rows=len(score_rows),
        created=result["updated"],  # "created" in this context = positions updated
        not_found=result["not_found"],
        errors=result["errors"],
    )
