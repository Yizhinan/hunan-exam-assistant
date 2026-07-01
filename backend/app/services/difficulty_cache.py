"""
Pre-computed difficulty score cache.

Computes landing-difficulty scores for ALL active positions once,
normalizing against the full dataset. Eliminates per-request computation.

Usage:
    from app.services.difficulty_cache import get_cache
    cache = get_cache()
    cache.ensure_init(db)  # one-time init
    score = cache.get(pos_id)  # O(1) lookup
"""

import json
import logging
import os
import threading

from app.services.difficulty import get_tier

logger = logging.getLogger(__name__)

# Default cache file path (relative to backend directory)
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "difficulty_cache.json")


class DifficultyCache:
    """Thread-safe in-memory cache of pre-computed difficulty scores."""

    def __init__(self):
        self._lock = threading.Lock()
        self._scores: dict[str, dict] = {}
        self._initialized: bool = False
        self._year: int | None = None

    async def ensure_init(self, db=None, year: int | None = None) -> bool:
        """Ensure cache is initialized. Prefers fresh DB computation over stale JSON.

        When ``year`` is None (default), scores ALL active positions regardless of year.
        This is the recommended mode — single-year caches cause positions from other
        years to show the default 50.0 score.
        """
        if self._initialized and self._year == year:
            return False

        # Always compute from DB when available (more reliable than stale JSON)
        if db is not None:
            return await self.refresh(db, year)

        # Fall back to JSON file if no DB session
        cache_path = os.path.normpath(CACHE_FILE)
        if os.path.exists(cache_path):
            return self._load_from_file(cache_path)

        logger.warning("Difficulty cache not initialized: no JSON file and no DB session")
        return False

    def _load_from_file(self, path: str) -> bool:
        """Load precomputed scores from a JSON file."""
        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._scores = json.load(f)
                self._initialized = True
                logger.info("Difficulty cache loaded from %s: %d positions", path, len(self._scores))
                return True
            except Exception as e:
                logger.error("Failed to load difficulty cache from %s: %s", path, e)
                return False

    async def refresh(self, db, year: int | None = None) -> bool:
        """Recompute all difficulty scores in O(n) using pre-aggregated stats.
        Also loads cross-year data for historical trend bonus.
        Works with both sync (SQLite) and async (PostgreSQL) sessions.
        """
        from collections import defaultdict
        from app.models.position import PositionHistory
        from app.services.difficulty import (
            _normalize, get_exam_max_score, enrollment_score,
            _get_competition_ratio, CITY_COMPETITION_BASE,
            WEIGHT_ADMISSION, WEIGHT_COMPETITION,
            WEIGHT_ENROLLMENT, WEIGHT_TREND,
        )

        def _major_key(major: str | None) -> str | None:
            """Extract broad major category for cross-year comparison.

            "法学类,法律" → "法学"   "会计学,财务管理" → "会计学"
            "不限" → None          "" → None
            """
            if not major or "不限" in major:
                return None
            import re
            first = re.split(r'[，,、；;\s]+', major.strip())[0]
            # Take at most 4 chars to group similar majors (e.g. 计算机类 → 计算机)
            return first[:4] if len(first) > 4 else first

        # Detect session type — async sessions don't have .query()
        is_async = not hasattr(db, 'query')

        # Load current-year positions (for scoring)
        if is_async:
            from sqlalchemy import select as sa_select
            stmt = sa_select(PositionHistory).where(PositionHistory.is_active == True)
            if year:
                stmt = stmt.where(PositionHistory.year == year)
            result = await db.execute(stmt)
            all_positions = result.scalars().all()
        else:
            stmt = db.query(PositionHistory).filter(PositionHistory.is_active == True)
            if year:
                stmt = stmt.filter(PositionHistory.year == year)
            all_positions = stmt.all()

        # Load OTHER years' data for historical comparison (exclude current year)
        if is_async:
            from sqlalchemy import select as sa_select
            hist_stmt = sa_select(PositionHistory).where(
                PositionHistory.is_active == True,
                PositionHistory.min_score_interview.isnot(None),
            )
            if year:
                hist_stmt = hist_stmt.where(PositionHistory.year != year)
            hist_result = await db.execute(hist_stmt)
            historical_positions = hist_result.scalars().all()
        else:
            hist_stmt = db.query(PositionHistory).filter(
                PositionHistory.is_active == True,
                PositionHistory.min_score_interview != None,
            )
            if year:
                hist_stmt = hist_stmt.filter(PositionHistory.year != year)
            historical_positions = hist_stmt.all()

        with self._lock:

            if not all_positions:
                logger.warning("No positions found for difficulty pre-compute")
                return False

            # === O(n): pre-aggregate scored positions by (city, exam_type) ===
            # exam_type: "2科" or "3科" based on exam_subject
            city_exam_pcts: dict[tuple, list[float]] = defaultdict(list)  # (city, "2科"/"3科") → [pct, ...]
            exam_type_pcts: dict[str, list[float]] = defaultdict(list)    # "2科"/"3科" → [pct, ...]
            city_pcts: dict[str, list[float]] = defaultdict(list)         # city → [pct, ...]
            all_scored_pcts: list[float] = []

            for pos in all_positions:
                s = getattr(pos, 'min_score_interview', None)
                if s is None:
                    continue
                max_s = get_exam_max_score(getattr(pos, 'exam_subject', None), float(s))
                pct = float(s) / max_s * 100.0  # 转百分制
                exam_type = "3科" if max_s == 300 else "2科"
                city = getattr(pos, 'city', '')

                city_exam_pcts[(city, exam_type)].append(pct)
                exam_type_pcts[exam_type].append(pct)
                city_pcts[city].append(pct)
                all_scored_pcts.append(pct)

            # Pre-computed averages for O(1) estimation
            city_exam_pct_avg = {k: sum(v) / len(v) for k, v in city_exam_pcts.items()}
            exam_global_pct_avg = {k: sum(v) / len(v) for k, v in exam_type_pcts.items()}
            city_pct_avg = {k: sum(v) / len(v) for k, v in city_pcts.items()}
            global_pct_avg = sum(all_scored_pcts) / len(all_scored_pcts) if all_scored_pcts else 33.0

            # === Historical bonus: cross-year department+major vs city baseline ===
            # Key insight: same department + same major in past years predicts this year's difficulty.
            # e.g. 岳阳监狱 + 法学 historically scored lower than 岳阳 average → easier → negative bonus.
            dept_hist_pcts: dict[str, list[float]] = defaultdict(list)
            dept_major_hist_pcts: dict[tuple, list[float]] = defaultdict(list)
            city_exam_hist_pcts: dict[tuple, list[float]] = defaultdict(list)

            for pos in historical_positions:
                s = float(getattr(pos, 'min_score_interview', 0))
                max_s = get_exam_max_score(getattr(pos, 'exam_subject', None), s)
                pct = s / max_s * 100.0
                exam_type = "3科" if max_s == 300 else "2科"
                dept = getattr(pos, 'department', '')
                city = getattr(pos, 'city', '')
                mk = _major_key(getattr(pos, 'major_requirement', None))

                dept_hist_pcts[dept].append(pct)
                if mk:
                    dept_major_hist_pcts[(dept, mk)].append(pct)
                city_exam_hist_pcts[(city, exam_type)].append(pct)

            dept_hist_avg = {k: sum(v) / len(v) for k, v in dept_hist_pcts.items()}
            dept_major_hist_avg = {k: sum(v) / len(v) for k, v in dept_major_hist_pcts.items()}
            city_exam_hist_avg = {k: sum(v) / len(v) for k, v in city_exam_hist_pcts.items()}

            def get_trend_adjustment(pos) -> float:
                """Cross-year trend: how much easier/harder this (dept, major) was in past years.

                Three-level fallback:
                  L1: Same department + same broad major category
                  L2: Same department (any major)
                  L3: 0 (no historical data)

                Returns value in [-10, 10]. Negative = historically easier (< 0 风险).
                """
                dept = getattr(pos, 'department', '')
                city = getattr(pos, 'city', '')
                exam_type = "3科" if get_exam_max_score(getattr(pos, 'exam_subject', None)) == 300 else "2科"
                mk = _major_key(getattr(pos, 'major_requirement', None))

                city_exam_avg = city_exam_hist_avg.get((city, exam_type))
                if city_exam_avg is None:
                    return 0.0

                # L1: same dept + same major
                if mk:
                    dm_avg = dept_major_hist_avg.get((dept, mk))
                    if dm_avg is not None:
                        return max(-10.0, min(10.0, dm_avg - city_exam_avg))

                # L2: same dept (any major)
                dept_avg = dept_hist_avg.get(dept)
                if dept_avg is not None:
                    return max(-10.0, min(10.0, dept_avg - city_exam_avg))

                return 0.0

            def estimate_score_pct(pos) -> float:
                """O(1) 三级回退进面分估算（百分制），含历史修正."""
                s = getattr(pos, 'min_score_interview', None)
                if s is not None:
                    max_s = get_exam_max_score(getattr(pos, 'exam_subject', None), float(s))
                    return float(s) / max_s * 100.0

                exam_type = "3科" if get_exam_max_score(getattr(pos, 'exam_subject', None)) == 300 else "2科"
                city = getattr(pos, 'city', '')

                # L1: 同城市 + 同考试科目数
                key = (city, exam_type)
                if key in city_exam_pct_avg:
                    base = city_exam_pct_avg[key]
                elif exam_type in exam_global_pct_avg:
                    base = exam_global_pct_avg[exam_type]
                elif city in city_pct_avg:
                    base = city_pct_avg[city]
                else:
                    base = global_pct_avg

                # Apply trend bonus (dept+major historical deviation)
                trend = get_trend_adjustment(pos)
                return max(5.0, base + trend * 0.5)

            def estimate_ratio(pos) -> float:
                """O(1) 竞争比估算：真实数据优先，否则按城市+岗位特征."""
                applicants = getattr(pos, 'applicant_count', None)
                enroll = max(float(getattr(pos, 'enrollment_count', 1)), 1)
                if applicants is not None:
                    return float(applicants) / enroll

                city = getattr(pos, 'city', '')
                base = CITY_COMPETITION_BASE.get(city, 50.0)
                major = getattr(pos, 'major_requirement', None) or ""
                dept = getattr(pos, 'department', '') or ""

                ratio = base
                if not major or "不限" in major:
                    ratio *= 1.4
                if "公安" in dept:
                    ratio *= 0.6
                if enroll <= 1:
                    ratio *= 1.3
                elif enroll >= 5:
                    ratio *= 0.7
                elif enroll >= 3:
                    ratio *= 0.85
                return max(5.0, min(300.0, ratio))

            # === O(n): compute all values ===
            scores_pct = [estimate_score_pct(p) for p in all_positions]
            ratios = [estimate_ratio(p) for p in all_positions]
            enroll_factors = [enrollment_score(getattr(p, 'enrollment_count', 1) or 1) for p in all_positions]

            min_score, max_score = min(scores_pct), max(scores_pct)
            min_ratio, max_ratio = min(ratios), max(ratios)

            score_range = max_score - min_score
            ratio_range = max_ratio - min_ratio

            def fast_normalize(value: float, min_val: float, range_val: float) -> float:
                if range_val == 0:
                    return 50.0
                result = (value - min_val) / range_val * 100.0
                if result < 0.0:
                    return 0.0
                if result > 100.0:
                    return 100.0
                return result

            # === O(n): compute difficulty ===
            new_scores: dict[str, dict] = {}
            for i, pos in enumerate(all_positions):
                try:
                    admission_factor = fast_normalize(scores_pct[i], min_score, score_range)
                    competition_factor = fast_normalize(ratios[i], min_ratio, ratio_range)
                    enrollment_factor = enroll_factors[i]  # already 0-100
                    trend_adjustment = get_trend_adjustment(pos)

                    total = (
                        admission_factor * WEIGHT_ADMISSION
                        + competition_factor * WEIGHT_COMPETITION
                        + enrollment_factor * WEIGHT_ENROLLMENT
                        + trend_adjustment * WEIGHT_TREND
                    )
                    total = max(0.0, min(100.0, total))
                    tier = get_tier(total)

                    new_scores[str(pos.id)] = {
                        "score": round(total, 1),
                        "tier": tier,
                        "breakdown": {
                            "admission_score": round(admission_factor, 1),
                            "competition_ratio": round(competition_factor, 1),
                            "enrollment_scale": round(enrollment_factor, 1),
                            "trend_adjustment": round(trend_adjustment, 1),
                            "total": round(total, 1),
                        },
                    }
                except Exception as e:
                    logger.error(f"Failed for {pos.id}: {e}")
                    new_scores[str(pos.id)] = {
                        "score": 50.0, "tier": "稳妥", "breakdown": {},
                    }

            self._scores = new_scores
            self._initialized = True
            self._year = year
            logger.info(
                "Difficulty cache refreshed: %d positions (year=%s)",
                len(new_scores), year or "all",
            )

            # Persist to JSON file for fast startup next time
            try:
                cache_path = os.path.normpath(CACHE_FILE)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(new_scores, f, ensure_ascii=False)
                logger.info("Difficulty cache written to %s", cache_path)
            except Exception as e:
                logger.warning("Failed to persist difficulty cache: %s", e)

            return True

    def get(self, pos_id: str) -> dict | None:
        """Get pre-computed difficulty for a position. Thread-safe."""
        with self._lock:
            return self._scores.get(str(pos_id))

    def get_batch(self, pos_ids: list[str]) -> dict[str, dict]:
        """Get pre-computed scores for multiple positions."""
        with self._lock:
            return {
                pid: self._scores[pid]
                for pid in map(str, pos_ids)
                if pid in self._scores
            }

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._scores)

    @property
    def initialized(self) -> bool:
        return self._initialized


# Singleton
_cache: DifficultyCache | None = None


def get_cache() -> DifficultyCache:
    """Get or create the global difficulty cache singleton."""
    global _cache
    if _cache is None:
        _cache = DifficultyCache()
    return _cache
