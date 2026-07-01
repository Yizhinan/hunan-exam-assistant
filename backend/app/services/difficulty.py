"""
上岸难度评分引擎 — Landing Difficulty Scorer.

综合进面分(0.35) + 竞争比(0.25) + 招录规模(0.30) + 趋势修正(0.10)
生成 0-100 难度分，越低越容易上岸。

有真实进面分的岗位直接使用；无数据的岗位按城市+考试科目三级回退估算。
"""

from dataclasses import dataclass


@dataclass
class DifficultyBreakdown:
    """上岸难度分项明细."""
    admission_score: float   # 进面分因子 0-100
    competition_ratio: float # 竞争比因子 0-100
    enrollment_scale: float  # 招录规模因子 0-100（越大越难）
    trend_adjustment: float  # 趋势修正 -10 ~ +10
    total: float             # 加权总分 0-100
    tier: str                # 保底 / 稳妥 / 冲刺


WEIGHT_ADMISSION = 0.40
WEIGHT_COMPETITION = 0.15
WEIGHT_ENROLLMENT = 0.35
WEIGHT_TREND = 0.10

TIER_RECOMMENDED = "保底"
TIER_STABLE = "稳妥"
TIER_REACH = "冲刺"


# ============================================================
# 考试科目满分判断
# ============================================================
def get_exam_max_score(exam_subject: str | None, score: float | None = None) -> int:
    """判断该岗位笔试满分：2科=200，3科（含专业科目）=300.

    如果 exam_subject 为 NULL，通过分数推断：>100 大概率是 3 科满分 300。
    """
    if exam_subject:
        s = exam_subject.strip()
        if any(kw in s for kw in ("专业知识", "专业科目", "公安")):
            return 300
        return 200
    # NULL exam_subject: infer from score value
    if score is not None and score > 100:
        return 300
    return 200


# ============================================================
# 招录规模 → 难度分（非线性映射，拉开差距）
# ============================================================
def enrollment_score(enrollment_count: int) -> float:
    """
    招录人数越多越容易。非线性映射到 0-100 难度分。
    招1人=90(最难)，招10+人=5(最容易)。
    """
    if enrollment_count <= 0:
        return 90.0
    if enrollment_count >= 10:
        return 5.0
    if enrollment_count >= 6:
        return 15.0
    mapping = {1: 90, 2: 70, 3: 50, 4: 35, 5: 25}
    return float(mapping.get(enrollment_count, 15.0))


# ============================================================
# 城市竞争比基准（无真实报名数据时的估算）
# ============================================================
CITY_COMPETITION_BASE: dict[str, float] = {
    "长沙": 100, "株洲": 70, "湘潭": 65,
    "衡阳": 55, "岳阳": 55, "常德": 55,
    "邵阳": 40, "郴州": 40, "永州": 40, "益阳": 40,
    "娄底": 30, "怀化": 30, "张家界": 25, "湘西": 30,
    "省直": 80,
}


# ============================================================
# 归一化
# ============================================================
def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Min-Max 归一化到 0-100. 如果范围为零则返回 50（中性）."""
    if max_val <= min_val:
        return 50.0
    result = (value - min_val) / (max_val - min_val) * 100.0
    return max(0.0, min(100.0, result))


# ============================================================
# 三级回退：进面分估算（百分制）
# ============================================================
def _estimate_score_pct(
    city: str,
    exam_subject: str | None,
    all_positions,
    city_exam_pct_avg: dict | None = None,
    exam_global_pct_avg: dict | None = None,
    city_pct_avg: dict | None = None,
    global_pct_avg: float = 33.0,
) -> float:
    """
    估算岗位进面分（百分制）。

    三级回退：
      L1: 同城市 + 同考试科目数（2科/3科）有分岗位的百分制均值
      L2: 同考试科目数全局百分制均值
      L3: 该城市全部岗位百分制均值
      L4: 全局百分制均值

    如果传入了预计算的聚合字典（来自 cache.refresh），走 O(1) 查表；
    否则遍历 all_positions 计算（用于单岗位 compute_difficulty）。
    """
    exam_type = "3科" if get_exam_max_score(exam_subject) == 300 else "2科"

    # 有预聚合数据 → O(1)
    if city_exam_pct_avg is not None:
        key = (city, exam_type)
        if key in city_exam_pct_avg:
            return city_exam_pct_avg[key]
        if exam_type in exam_global_pct_avg:
            return exam_global_pct_avg[exam_type]
        if city in city_pct_avg:
            return city_pct_avg[city]
        return global_pct_avg

    # 无预聚合数据 → 遍历计算（单岗位场景）
    same_city_exam = []
    same_exam = []
    same_city_all = []
    all_scored = []

    for p in all_positions:
        s = getattr(p, 'min_score_interview', None)
        if s is None:
            continue
        p_exam_type = "3科" if get_exam_max_score(getattr(p, 'exam_subject', None)) == 300 else "2科"
        p_city = getattr(p, 'city', '')
        pct = float(s) / get_exam_max_score(getattr(p, 'exam_subject', None)) * 100.0

        all_scored.append(pct)
        if p_city == city and p_exam_type == exam_type:
            same_city_exam.append(pct)
        if p_exam_type == exam_type:
            same_exam.append(pct)
        if p_city == city:
            same_city_all.append(pct)

    if same_city_exam:
        return sum(same_city_exam) / len(same_city_exam)
    if same_exam:
        return sum(same_exam) / len(same_exam)
    if same_city_all:
        return sum(same_city_all) / len(same_city_all)
    if all_scored:
        return sum(all_scored) / len(all_scored)
    return global_pct_avg


# ============================================================
# 竞争比估算
# ============================================================
def _get_competition_ratio(position, all_positions, city_base_map: dict | None = None) -> float:
    """
    获取竞争比。有真实报名数据直接用，无数据按城市+特征估算。
    """
    applicants = getattr(position, 'applicant_count', None)
    enroll = max(float(getattr(position, 'enrollment_count', 1)), 1)

    # 有真实数据 → 直接返回
    if applicants is not None:
        return float(applicants) / enroll

    # 无真实数据 → 按城市+岗位特征估算
    city = getattr(position, 'city', '')
    base_map = city_base_map or CITY_COMPETITION_BASE
    base = base_map.get(city, 50.0)

    # 岗位特征修正
    major = getattr(position, 'major_requirement', None) or ""
    dept = getattr(position, 'department', '') or ""

    ratio = base
    # 专业不限 → 报名更多
    if not major or major == "不限" or "不限" in major:
        ratio *= 1.4
    # 公安系统 → 限制多，报名较少
    if "公安" in dept:
        ratio *= 0.6
    # 招录人数修正：招得少竞争更激烈
    if enroll <= 1:
        ratio *= 1.3
    elif enroll >= 5:
        ratio *= 0.7
    elif enroll >= 3:
        ratio *= 0.85

    return max(5.0, min(300.0, ratio))


# ============================================================
# 单岗位难度计算
# ============================================================
def compute_difficulty(position, all_positions, trend_data=None) -> DifficultyBreakdown:
    """
    计算单岗位上岸难度。

    有真实进面分 → 直接使用；无数据 → 三级回退估算。
    竞争比同理。
    """
    # 1. 进面分因子（百分制）
    real_score = getattr(position, 'min_score_interview', None)
    max_s = get_exam_max_score(getattr(position, 'exam_subject', None))
    if real_score is not None:
        score_pct = float(real_score) / max_s * 100.0
    else:
        score_pct = _estimate_score_pct(
            getattr(position, 'city', ''),
            getattr(position, 'exam_subject', None),
            all_positions,
        )

    # 所有岗位的百分制分数
    all_pct = []
    for p in all_positions:
        s = getattr(p, 'min_score_interview', None)
        ms = get_exam_max_score(getattr(p, 'exam_subject', None))
        if s is not None:
            all_pct.append(float(s) / ms * 100.0)
        else:
            all_pct.append(_estimate_score_pct(
                getattr(p, 'city', ''),
                getattr(p, 'exam_subject', None),
                all_positions,
            ))

    admission_factor = _normalize(score_pct, min(all_pct), max(all_pct))

    # 2. 竞争比因子
    ratio = _get_competition_ratio(position, all_positions)
    all_ratios = [_get_competition_ratio(p, all_positions) for p in all_positions]
    competition_factor = _normalize(ratio, min(all_ratios), max(all_ratios))

    # 3. 招录规模因子（非线性映射）
    enroll = getattr(position, 'enrollment_count', 1) or 1
    enrollment_factor = enrollment_score(enroll)

    # 4. 趋势修正
    if trend_data:
        pos_id = getattr(position, 'id', None)
        delta = trend_data.get(str(pos_id), 0.0) if pos_id else 0.0
    else:
        delta = 0.0
    trend_adjustment = max(-10.0, min(10.0, delta))

    # 加权
    total = (
        admission_factor * WEIGHT_ADMISSION
        + competition_factor * WEIGHT_COMPETITION
        + enrollment_factor * WEIGHT_ENROLLMENT
        + trend_adjustment * WEIGHT_TREND
    )
    total = max(0.0, min(100.0, total))
    tier = get_tier(total)

    return DifficultyBreakdown(
        admission_score=round(admission_factor, 1),
        competition_ratio=round(competition_factor, 1),
        enrollment_scale=round(enrollment_factor, 1),
        trend_adjustment=round(trend_adjustment, 1),
        total=round(total, 1),
        tier=tier,
    )


# ============================================================
# 批量计算
# ============================================================
def compute_batch_difficulties(positions, trend_map=None):
    """批量计算难度分，按难度升序返回."""
    results = []
    for pos in positions:
        breakdown = compute_difficulty(pos, positions, trend_map)
        results.append((pos, breakdown))
    results.sort(key=lambda x: x[1].total)
    return results


# ============================================================
# 三档分类
# ============================================================
def get_tier(score: float) -> str:
    if score <= 25:
        return TIER_RECOMMENDED
    elif score <= 50:
        return TIER_STABLE
    return TIER_REACH
