"""
上岸难度评分引擎 — Landing Difficulty Scorer.

综合进面分(0.40) + 竞争比(0.35) + 招录规模(0.15) + 趋势修正(0.10)
生成 0-100 难度分，越低越容易上岸。
"""

from dataclasses import dataclass


@dataclass
class DifficultyBreakdown:
    """上岸难度分项明细."""
    admission_score: float   # 进面分因子 0-100
    competition_ratio: float # 竞争比因子 0-100
    enrollment_scale: float  # 招录规模因子 0-100
    trend_adjustment: float  # 趋势修正 -10 ~ +10
    total: float             # 加权总分 0-100
    tier: str                # 保底 / 稳妥 / 冲刺


WEIGHT_ADMISSION = 0.40
WEIGHT_COMPETITION = 0.35
WEIGHT_ENROLLMENT = 0.15
WEIGHT_TREND = 0.10

TIER_RECOMMENDED = "保底"
TIER_STABLE = "稳妥"
TIER_REACH = "冲刺"


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Min-Max 归一化到 0-100. 如果范围为零则返回 50（中性）."""
    if max_val <= min_val:
        return 50.0
    result = (value - min_val) / (max_val - min_val) * 100.0
    return max(0.0, min(100.0, result))


def _estimate_missing_score(city: str, exam_category: str, all_positions) -> float:
    """用同城市同类别的均分估算缺失的进面分."""
    same = [
        p for p in all_positions
        if getattr(p, 'city', None) == city
        and getattr(p, 'exam_category', None) == exam_category
        and getattr(p, 'min_score_interview', None) is not None
    ]
    if not same:
        # fallback: 全量均分
        all_scored = [p for p in all_positions if getattr(p, 'min_score_interview', None) is not None]
        if all_scored:
            return sum(p.min_score_interview for p in all_scored) / len(all_scored)
        return 130.0
    return sum(p.min_score_interview for p in same) / len(same)


def _get_score(position, all_positions) -> float:
    """Get min_score_interview or estimate."""
    score = getattr(position, 'min_score_interview', None)
    if score is not None:
        return float(score)
    city = getattr(position, 'city', '')
    cat = getattr(position, 'exam_category', '')
    return _estimate_missing_score(city, cat, all_positions)


def _get_competition_ratio(position, all_positions) -> float:
    """Get competition ratio or estimate from category mean."""
    applicants = getattr(position, 'applicant_count', None)
    enroll = getattr(position, 'enrollment_count', 1)
    if applicants is not None and enroll > 0:
        return float(applicants) / float(enroll)
    # Estimate from same category
    cat = getattr(position, 'exam_category', None)
    same = [
        p for p in all_positions
        if getattr(p, 'exam_category', None) == cat
        and getattr(p, 'applicant_count', None) is not None
    ]
    if same:
        avg = sum(float(p.applicant_count) / max(float(p.enrollment_count), 1) for p in same) / len(same)
        return avg
    return 100.0  # default moderate


def compute_difficulty(position, all_positions, trend_data=None) -> DifficultyBreakdown:
    """
    Compute landing difficulty score for a single position.

    Args:
        position: PositionHistory ORM object with min_score_interview, applicant_count, enrollment_count
        all_positions: list of all PositionHistory objects in the matching set
        trend_data: optional dict of {position_id: trend_delta} from trend analysis

    Returns:
        DifficultyBreakdown with scores 0-100 (lower = easier)
    """
    # 1. Admission score factor
    score = _get_score(position, all_positions)
    all_scores = [_get_score(p, all_positions) for p in all_positions]
    admission_factor = _normalize(score, min(all_scores), max(all_scores))

    # 2. Competition ratio factor
    ratio = _get_competition_ratio(position, all_positions)
    all_ratios = [_get_competition_ratio(p, all_positions) for p in all_positions]
    competition_factor = _normalize(ratio, min(all_ratios), max(all_ratios))

    # 3. Enrollment scale factor (1 / enrollment → more slots = easier)
    enroll = max(float(getattr(position, 'enrollment_count', 1)), 1)
    all_enrolls = [max(float(getattr(p, 'enrollment_count', 1)), 1) for p in all_positions]
    # Invert: more slots → lower score
    inv_enroll = 1.0 / enroll
    all_inv = [1.0 / e for e in all_enrolls]
    enrollment_factor = _normalize(inv_enroll, min(all_inv), max(all_inv))

    # 4. Trend adjustment
    if trend_data:
        pos_id = getattr(position, 'id', None)
        delta = trend_data.get(str(pos_id), 0.0) if pos_id else 0.0
    else:
        delta = 0.0
    # delta > 0 means score is going up (harder) → positive adjustment
    # delta < 0 means score is going down (easier) → negative adjustment
    trend_adjustment = max(-10.0, min(10.0, delta))

    # Weighted total
    total = (
        admission_factor * WEIGHT_ADMISSION
        + competition_factor * WEIGHT_COMPETITION
        + enrollment_factor * WEIGHT_ENROLLMENT
        + trend_adjustment * WEIGHT_TREND
    )
    total = max(0.0, min(100.0, total))

    # Tier (use public helper)
    tier = get_tier(total)

    return DifficultyBreakdown(
        admission_score=round(admission_factor, 1),
        competition_ratio=round(competition_factor, 1),
        enrollment_scale=round(enrollment_factor, 1),
        trend_adjustment=round(trend_adjustment, 1),
        total=round(total, 1),
        tier=tier,
    )


def compute_batch_difficulties(positions, trend_map=None):
    """
    Compute difficulty for a batch of positions.

    Args:
        positions: list of PositionHistory objects
        trend_map: optional dict of {position_id: trend_delta}

    Returns:
        list of (position, DifficultyBreakdown) sorted by difficulty ascending
    """
    results = []
    for pos in positions:
        breakdown = compute_difficulty(pos, positions, trend_map)
        results.append((pos, breakdown))
    results.sort(key=lambda x: x[1].total)
    return results


def get_tier(score: float) -> str:
    if score <= 35:
        return TIER_RECOMMENDED
    elif score <= 65:
        return TIER_STABLE
    return TIER_REACH
