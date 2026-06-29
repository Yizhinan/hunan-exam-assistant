# 上岸难度评分 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 考情分析推荐引擎从「按进面分排序」升级为「综合上岸难度评分」，新增趋势接口、统计概览，前端结果页展示难度分环、趋势图、分层标签。

**Architecture:** 后端新增 `app/services/difficulty.py` 纯函数计算难度分，改造 `analysis.py` 的 recommend 返回难度字段，新增 trend/stats 端点。前端抽取 PositionCard/DifficultyRing 组件，改造 ResultPage 增加概览和趋势，FormPage 支持 URL 参数持久化。

**Tech Stack:** Python 3.14 / FastAPI / SQLAlchemy / Pydantic · React 18 / TypeScript / Tailwind / recharts / lucide-react

---

## Global Constraints

- Python 版本 3.14，使用 `sqlalchemy`（非 async 版本，本地 SQLite）
- 前端 TypeScript `^5.7.2`，React `^18.3.1`
- 组件文件放 `frontend/src/components/analysis/`
- CSS 使用项目已有 Tailwind utility 类（card, btn-*, input-field, tag 等）
- 后端返回使用 Pydantic `BaseModel`
- 不使用 pytest（项目无测试基建），后端用脚本手动验证

---

## File Structure

```
backend/app/services/__init__.py          [NEW] 模块占位
backend/app/services/difficulty.py        [NEW] 难度计算纯函数

backend/app/api/analysis.py               [MODIFY] recommend 加难度字段
                                          [MODIFY] 新增 /trend/{city}
                                          [MODIFY] 新增 /stats/overview

frontend/src/services/api.ts              [MODIFY] AnalysisResult/PositionOut 加难度字段
                                          [MODIFY] 新增 analysisApi.getTrend/getStats

frontend/src/components/analysis/
  DifficultyRing.tsx                      [NEW] 难度分环形图（SVG）
  PositionCard.tsx                        [NEW] 可复用岗位卡片 + 难度分圆环 + 分层标签
  StatsOverview.tsx                       [NEW] 结果页概览统计卡片行
  TrendChart.tsx                          [NEW] recharts 趋势折线图

frontend/src/pages/Analysis/
  FormPage.tsx                            [MODIFY] URL search params 持久化
  ResultPage.tsx                          [MODIFY] 概览卡片 + PositionCard 替换 + 趋势图
```

---

### Task 1: 难度计算服务

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/difficulty.py`

**Interfaces:**
- Produces:
  - `DifficultyBreakdown` dataclass — `{admission_score, competition_ratio, enrollment_scale, trend_adjustment, total}`
  - `compute_difficulty(position, all_positions, trend_data=None) -> DifficultyBreakdown`
  - `compute_batch_difficulties(positions, trend_map=None) -> list[tuple[Position, DifficultyBreakdown]]`
  - `get_tier(score: float) -> str` 返回 "保底"/"稳妥"/"冲刺"
  - 内部辅助: `_normalize(value, min_val, max_val) -> float`, `_estimate_missing_score(position, all_positions) -> float`

- [ ] **Step 1: Create services package init**

Create `backend/app/services/__init__.py`:
```python
"""Business logic services."""
```

- [ ] **Step 2: Write difficulty.py — dataclasses and utility functions**

Create `backend/app/services/difficulty.py`:
```python
"""
上岸难度评分引擎 — Landing Difficulty Scorer.

综合进面分(0.40) + 竞争比(0.35) + 招录规模(0.15) + 趋势修正(0.10)
生成 0-100 难度分，越低越容易上岸。
"""

from dataclasses import dataclass, field


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

    # Tier
    if total <= 35:
        tier = TIER_RECOMMENDED
    elif total <= 65:
        tier = TIER_STABLE
    else:
        tier = TIER_REACH

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
```

- [ ] **Step 3: Verify with a quick inline test**

Run from `backend/`:
```bash
python -c "
import sys; sys.path.insert(0, '.')
import os; os.environ['DATABASE_URL'] = 'sqlite:///hunan_exam.db'
from app.services.difficulty import *
from dataclasses import dataclass

# Mock positions
@dataclass
class MockPos:
    id: str; city: str; exam_category: str
    min_score_interview: float | None
    applicant_count: int | None
    enrollment_count: int

p1 = MockPos('a','长沙','省市直',135.0,300,2)
p2 = MockPos('b','株洲','行政执法',128.0,200,5)
p3 = MockPos('c','湘西','县乡基层',120.0,150,8)
all_pos = [p1, p2, p3]

b = compute_difficulty(p1, all_pos)
assert b.tier in ('保底','稳妥','冲刺'), f'bad tier: {b.tier}'
assert 0 <= b.total <= 100, f'total out of range: {b.total}'

# p3 should be easiest (lowest score, most slots)
b3 = compute_difficulty(p3, all_pos)
b1 = compute_difficulty(p1, all_pos)
assert b3.total < b1.total, f'p3 should be easier: {b3.total} vs {b1.total}'

batch = compute_batch_difficulties(all_pos)
assert batch[0][0].id == 'c', f'easiest should be c, got {batch[0][0].id}'

print('PASS: all assertions')
"
```

Expected output: `PASS: all assertions`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/difficulty.py
git commit -m "feat: add landing difficulty scoring service"
```

---

### Task 2: 改造 POST /recommend 加入难度分

**Files:**
- Modify: `backend/app/api/analysis.py`

**Interfaces:**
- Consumes: `from app.services.difficulty import compute_batch_difficulties, DifficultyBreakdown`
- Modifies: `PositionOut` Pydantic model — 新增 3 字段
- Modifies: `recommend_positions` — 排序逻辑改为按难度分

- [ ] **Step 1: Update PositionOut model**

In `backend/app/api/analysis.py`, at `class PositionOut(BaseModel):` add three fields after `predicted_score`:

```python
class PositionOut(BaseModel):
    # ... existing fields remain ...
    predicted_score: float | None
    # 新增 — 上岸难度
    difficulty_score: float  # 0-100, 越低越容易
    difficulty_breakdown: dict  # {admission_score, competition_ratio, enrollment_scale, trend_adjustment, total}
    tier: str  # 保底 / 稳妥 / 冲刺
```

- [ ] **Step 2: Update import and modify recommend_positions sort logic**

At the top of `analysis.py`, add:
```python
from app.services.difficulty import compute_batch_difficulties
```

Replace the current sort logic. Find the section starting from the `sort_key` function definition (~line 169) through the end of the ranking loop and replace. The key change: after collecting matched positions, call `compute_batch_difficulties` and sort by difficulty:

```python
    # === 难度评分与排序 ===
    # Collect all candidate positions
    candidates_raw = matched  # list of (pos, score, details)

    # Flatten candidates list for difficulty computation
    candidate_positions = [item[0] for item in ranked]
    difficulty_map = {}
    if candidate_positions:
        diff_results = compute_batch_difficulties(candidate_positions)
        difficulty_map = {p.id: b for p, b in diff_results}
        # Re-sort ranked by difficulty total
        def diff_sort_key(item):
            pos, score, details = item
            d = difficulty_map.get(pos.id)
            return d.total if d else 50.0
        ranked.sort(key=diff_sort_key)
```

- [ ] **Step 3: Add difficulty fields to the PositionOut construction**

In the `for pos, score, details in ranked[:20]:` loop, add difficulty fields:

```python
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
```

And in the `PositionOut(...)` call, add:
```python
            difficulty_score=diff_score,
            difficulty_breakdown=diff_breakdown,
            tier=tier,
```

- [ ] **Step 4: Update the tier variable name conflict**

The existing code uses `risk_level = "高" if ...`. The new tier is different from risk_level. Keep both: `risk_level` is about predicted score risk, `tier` is about landing difficulty. Add `tier=tier` to the PositionOut call.

- [ ] **Step 5: Verify**

Run from `backend/`:
```bash
python -c "
import sys; sys.path.insert(0, '.')
import os; os.environ['DATABASE_URL'] = 'sqlite:///hunan_exam.db'
from app.core.database import SessionLocal
from app.services.difficulty import compute_batch_difficulties
from app.models.position import PositionHistory

db = SessionLocal()
positions = db.execute(
    __import__('sqlalchemy').select(PositionHistory).where(PositionHistory.is_active == True)
).scalars().all()
print(f'Total positions: {len(positions)}')

results = compute_batch_difficulties(positions)
for pos, b in results[:5]:
    print(f'{pos.city} {pos.position_name} | 难度={b.total} | {b.tier} | 进面={b.admission_score} 竞争={b.competition_ratio} 规模={b.enrollment_scale}')
db.close()
"
```

Expected: 5 positions printed with tier labels, all difficulty scores 0-100.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/analysis.py
git commit -m "feat: integrate difficulty scoring into position recommendations"
```

---

### Task 3: 新增 GET /trend/{city} 和 GET /stats/overview

**Files:**
- Modify: `backend/app/api/analysis.py` (追加两个端点)

**Interfaces:**
- Produces:
  - `GET /api/analysis/trend/{city}` → `{city, data: [{year, avg_score, count}]}`
  - `GET /api/analysis/stats/overview` → `{by_city, by_category, easiest_city, easiest_category}`

- [ ] **Step 1: Add trend endpoint**

Append to `analysis.py`, before the last line of the file:

```python
@router.get("/trend/{city}")
async def get_city_trend(
    city: str,
    category: str | None = Query(None),
    db: Session = Depends(get_db),
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

    rows = db.execute(query).all()
    data = [
        {"year": row[0], "avg_score": round(float(row[1]), 1), "count": row[2]}
        for row in rows
    ]

    return {"city": city, "category": category, "data": data}


@router.get("/stats/overview")
async def get_stats_overview(db: Session = Depends(get_db)):
    """Get aggregate statistics for all positions."""
    # By city
    city_rows = db.execute(
        select(
            PositionHistory.city,
            func.avg(PositionHistory.min_score_interview),
            func.count(PositionHistory.id),
        ).where(
            PositionHistory.is_active == True,
            PositionHistory.min_score_interview.isnot(None),
        ).group_by(PositionHistory.city).order_by(PositionHistory.city)
    ).all()

    by_city = [
        {"city": row[0], "avg_score": round(float(row[1]), 1), "count": row[2]}
        for row in city_rows
    ]

    # By category
    cat_rows = db.execute(
        select(
            PositionHistory.exam_category,
            func.avg(PositionHistory.min_score_interview),
            func.count(PositionHistory.id),
        ).where(
            PositionHistory.is_active == True,
            PositionHistory.min_score_interview.isnot(None),
        ).group_by(PositionHistory.exam_category).order_by(PositionHistory.exam_category)
    ).all()

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
```

- [ ] **Step 2: Verify**

Start backend or run:
```bash
# From backend/ directory, start uvicorn
cd backend && uvicorn app.main:app --reload --port 8000
```

Test with curl (in another terminal):
```bash
curl http://localhost:8000/api/analysis/trend/长沙
curl http://localhost:8000/api/analysis/stats/overview
```

Expected: JSON with trend data and stats.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/analysis.py
git commit -m "feat: add city trend and stats overview endpoints"
```

---

### Task 4: 前端 API 类型同步

**Files:**
- Modify: `frontend/src/services/api.ts`

**Interfaces:**
- Consumes: backend API response shapes
- Produces: Updated TypeScript types + new API methods

- [ ] **Step 1: Update PositionOut interface**

In `frontend/src/services/api.ts`, add to `PositionOut`:
```typescript
export interface DifficultyBreakdown {
  admission_score: number;
  competition_ratio: number;
  enrollment_scale: number;
  trend_adjustment: number;
  total: number;
}

export interface PositionOut {
  // ... all existing fields stay ...
  predicted_score: number | null;
  // 新增
  difficulty_score: number;
  difficulty_breakdown: DifficultyBreakdown;
  tier: string;  // "保底" | "稳妥" | "冲刺"
}
```

- [ ] **Step 2: Add Trend and Stats types**

After the existing type definitions, add:

```typescript
export interface TrendDataPoint {
  year: number;
  avg_score: number;
  count: number;
}

export interface CityTrend {
  city: string;
  category: string | null;
  data: TrendDataPoint[];
}

export interface StatsByItem {
  city?: string;
  category?: string;
  avg_score: number;
  count: number;
}

export interface StatsOverview {
  by_city: StatsByItem[];
  by_category: StatsByItem[];
  easiest_city: string;
  easiest_category: string;
}
```

- [ ] **Step 3: Add new API methods**

In the `analysisApi` object, add:

```typescript
  getTrend: (city: string, category?: string) =>
    api.get<CityTrend>(`/analysis/trend/${city}${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  getStats: () =>
    api.get<StatsOverview>("/analysis/stats/overview"),
```

And remove the stub `getCityTrend` that was calling the nonexistent endpoint:
```typescript
// REMOVE this line:
  getCityTrend: (city: string, category?: string) =>
    api.get(`/analysis/trend/${city}${category ? `?category=${category}` : ""}`),
```

- [ ] **Step 4: TypeScript compile check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: sync frontend API types with difficulty scoring + new endpoints"
```

---

### Task 5: DifficultyRing 组件

**Files:**
- Create: `frontend/src/components/analysis/DifficultyRing.tsx`

**Interfaces:**
- Produces: `<DifficultyRing score={number} tier={string} size={number} />` — SVG 环形进度条

- [ ] **Step 1: Write component**

Create `frontend/src/components/analysis/DifficultyRing.tsx`:

```tsx
interface DifficultyRingProps {
  score: number;       // 0-100
  tier: "保底" | "稳妥" | "冲刺";
  size?: number;       // default 72
}

const TIER_STYLE: Record<string, { stroke: string; bg: string; text: string }> = {
  "保底": { stroke: "#16a34a", bg: "#dcfce7", text: "text-emerald-600" },
  "稳妥": { stroke: "#d97706", bg: "#fef3c7", text: "text-amber-600" },
  "冲刺": { stroke: "#dc2626", bg: "#fee2e2", text: "text-red-600" },
};

export default function DifficultyRing({ score, tier, size = 72 }: DifficultyRingProps) {
  const style = TIER_STYLE[tier] || TIER_STYLE["稳妥"];
  const radius = (size - 6) / 2;
  const circumference = radius * Math.PI * 2;
  const dashOffset = circumference * (1 - score / 100);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        className="transform -rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="5"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={style.stroke}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-lg font-bold ${style.text}`}>{Math.round(score)}</span>
        <span className="text-[10px] text-warm-400 leading-none mt-0.5">{tier}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify by importing in a page and checking the build**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/analysis/DifficultyRing.tsx
git commit -m "feat: add DifficultyRing component for landing difficulty display"
```

---

### Task 6: PositionCard 可复用组件

**Files:**
- Create: `frontend/src/components/analysis/PositionCard.tsx`

**Interfaces:**
- Produces: `<PositionCard pos={PositionOut}>` — 岗位卡片含难度分圆环、分层标签、因子展开

- [ ] **Step 1: Write component**

Create `frontend/src/components/analysis/PositionCard.tsx`:

```tsx
import { Shield, CheckCircle2, AlertTriangle } from "lucide-react";
import DifficultyRing from "./DifficultyRing";
import type { PositionOut } from "../../services/api";

const TIER_CONFIG: Record<string, { color: string; bg: string; label: string; icon: typeof Shield }> = {
  "保底": { color: "text-emerald-600", bg: "bg-emerald-50", label: "容易上岸", icon: CheckCircle2 },
  "稳妥": { color: "text-amber-600", bg: "bg-amber-50", label: "正常发挥", icon: AlertTriangle },
  "冲刺": { color: "text-red-600", bg: "bg-red-50", label: "需要冲刺", icon: AlertTriangle },
};

const CATEGORY_LABELS: Record<string, string> = {
  "省市直": "省市直岗", "行政执法": "行政执法岗", "县乡基层": "县乡基层岗", "综合通用": "综合",
};

export default function PositionCard({ pos }: { pos: PositionOut }) {
  const tierStyle = TIER_CONFIG[pos.tier] || TIER_CONFIG["稳妥"];
  const TierIcon = tierStyle.icon;

  return (
    <div className="card p-5 hover:shadow-elevated transition-shadow">
      {/* Header row: location + category + tier + difficulty ring */}
      <div className="flex items-start gap-4">
        <DifficultyRing score={pos.difficulty_score} tier={pos.tier as "保底" | "稳妥" | "冲刺"} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-medium bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
              {pos.city_label}
            </span>
            <span className="text-xs text-warm-400">
              {CATEGORY_LABELS[pos.exam_category] || pos.exam_category}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${tierStyle.bg} ${tierStyle.color}`}>
              <TierIcon className="h-3 w-3 inline mr-0.5" />{tierStyle.label}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              pos.risk_level === "低" ? "bg-emerald-50 text-emerald-600" :
              pos.risk_level === "中" ? "bg-amber-50 text-amber-600" :
              "bg-red-50 text-red-600"
            }`}>
              {pos.risk_level === "低" ? "竞争温和" : pos.risk_level === "中" ? "有一定竞争" : "竞争激烈"}
            </span>
          </div>
          <h3 className="font-semibold text-warm-900">{pos.department}</h3>
          <p className="text-sm text-warm-500">{pos.position_name}</p>
        </div>
        <div className="shrink-0 text-right">
          <div className={`text-xl font-bold ${
            pos.match_score >= 80 ? "text-emerald-600" :
            pos.match_score >= 60 ? "text-brand-600" : "text-amber-600"
          }`}>{pos.match_score}</div>
          <div className="text-[10px] text-warm-400">匹配度</div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3 mt-4">
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-brand-600">{pos.predicted_score ?? "-"}</div>
          <div className="text-[10px] text-warm-400">预测进面分</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-warm-700">{pos.avg_score_interview ?? "-"}</div>
          <div className="text-[10px] text-warm-400">{pos.year}年均分</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-warm-700">{pos.competition_ratio ?? "-"}:1</div>
          <div className="text-[10px] text-warm-400">竞争比</div>
        </div>
        <div className="bg-warm-50 rounded-xl p-2.5 text-center">
          <div className="text-sm font-bold text-warm-700">{pos.enrollment_count}</div>
          <div className="text-[10px] text-warm-400">招录人数</div>
        </div>
      </div>

      {/* Requirements tags */}
      <div className="flex flex-wrap gap-1.5 mt-3 text-[11px] text-warm-500">
        <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.education_requirement}</span>
        <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.degree_requirement}</span>
        <span className="bg-warm-100 px-2 py-0.5 rounded">
          {pos.major_requirement || "专业不限"}
        </span>
        <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.political_requirement}</span>
        {pos.gender_requirement !== "不限" && (
          <span className="bg-warm-100 px-2 py-0.5 rounded">{pos.gender_requirement}</span>
        )}
      </div>

      {/* Expandable: match details + difficulty breakdown */}
      <details className="mt-3 text-xs">
        <summary className="text-warm-400 cursor-pointer hover:text-warm-600">
          匹配详情 & 难度分项
        </summary>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Match details */}
          <div className="space-y-0.5">
            <div className="text-[11px] font-medium text-warm-500 mb-1">匹配分析</div>
            {pos.match_details.map((d, i) => (
              <div key={i} className={d.startsWith("✅") ? "text-emerald-700" : d.startsWith("❌") ? "text-red-600" : "text-amber-600"}>
                {d}
              </div>
            ))}
          </div>
          {/* Difficulty breakdown */}
          {pos.difficulty_breakdown && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-medium text-warm-500 mb-1">难度分项（越低越容易）</div>
              <div className="flex justify-between text-warm-600">
                <span>进面分因子</span>
                <span className="font-medium">{pos.difficulty_breakdown.admission_score}</span>
              </div>
              <div className="flex justify-between text-warm-600">
                <span>竞争比因子</span>
                <span className="font-medium">{pos.difficulty_breakdown.competition_ratio}</span>
              </div>
              <div className="flex justify-between text-warm-600">
                <span>招录规模因子</span>
                <span className="font-medium">{pos.difficulty_breakdown.enrollment_scale}</span>
              </div>
              <div className="flex justify-between text-warm-600">
                <span>趋势修正</span>
                <span className="font-medium">{pos.difficulty_breakdown.trend_adjustment}</span>
              </div>
              <div className="flex justify-between text-warm-700 font-semibold border-t border-warm-100 pt-1 mt-1">
                <span>综合难度分</span>
                <span>{pos.difficulty_breakdown.total}</span>
              </div>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/analysis/PositionCard.tsx
git commit -m "feat: add reusable PositionCard with difficulty ring and breakdown"
```

---

### Task 7: StatsOverview 组件

**Files:**
- Create: `frontend/src/components/analysis/StatsOverview.tsx`

**Interfaces:**
- Produces: `<StatsOverview stats={StatsOverview} matchedCount={number} totalCount={number} tierCounts={Record} />` — 结果页顶部统计卡片行

- [ ] **Step 1: Write component**

Create `frontend/src/components/analysis/StatsOverview.tsx`:

```tsx
import { Target, TrendingDown, MapPin, Layers } from "lucide-react";
import type { StatsOverview as StatsOverviewType } from "../../services/api";

interface Props {
  stats: StatsOverviewType | null;
  matchedCount: number;
  totalCount: number;
  tierCounts: Record<string, number>;
}

export default function StatsOverview({ stats, matchedCount, totalCount, tierCounts }: Props) {
  const cards = [
    {
      icon: Target,
      label: "符合条件的岗位",
      value: `${matchedCount} / ${totalCount}`,
      sub: `${totalCount > 0 ? Math.round(matchedCount / totalCount * 100) : 0}% 可报考`,
      color: "text-brand-600",
      bg: "bg-brand-50",
    },
    {
      icon: TrendingDown,
      label: "最容易上岸的城市",
      value: stats?.easiest_city || "-",
      sub: stats?.by_city.find(c => c.city === stats.easiest_city)?.avg_score
        ? `平均进面 ${stats.by_city.find(c => c.city === stats.easiest_city)?.avg_score} 分`
        : "",
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
    {
      icon: Layers,
      label: "保底 / 稳妥 / 冲刺",
      value: `🟢${tierCounts["保底"] || 0} 🟡${tierCounts["稳妥"] || 0} 🔴${tierCounts["冲刺"] || 0}`,
      sub: stats?.easiest_category ? `最容易类别: ${stats.easiest_category}` : "",
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
    {
      icon: MapPin,
      label: "平均进面分",
      value: stats?.by_city.length
        ? `${Math.round(stats.by_city.reduce((s, c) => s + c.avg_score, 0) / stats.by_city.length)}`
        : "-",
      sub: "全省均值",
      color: "text-violet-600",
      bg: "bg-violet-50",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((card) => (
        <div key={card.label} className="card p-4">
          <div className={`w-8 h-8 rounded-xl ${card.bg} flex items-center justify-center mb-2`}>
            <card.icon className={`h-4 w-4 ${card.color}`} />
          </div>
          <div className="text-lg font-bold text-warm-900">{card.value}</div>
          <div className="text-[11px] text-warm-400 mt-0.5">{card.label}</div>
          {card.sub && <div className="text-[10px] text-warm-400 mt-0.5">{card.sub}</div>}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/analysis/StatsOverview.tsx
git commit -m "feat: add StatsOverview component for analysis result page"
```

---

### Task 8: TrendChart 组件

**Files:**
- Create: `frontend/src/components/analysis/TrendChart.tsx`

**Interfaces:**
- Produces: `<TrendChart data={TrendDataPoint[]} />` — recharts 折线图显示历年进面分趋势

- [ ] **Step 1: Write component**

Create `frontend/src/components/analysis/TrendChart.tsx`:

```tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { TrendDataPoint } from "../../services/api";

interface Props {
  data: TrendDataPoint[];
  className?: string;
}

export default function TrendChart({ data, className = "" }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className={`card p-5 ${className}`}>
        <p className="text-sm text-warm-400 text-center py-8">暂无趋势数据</p>
      </div>
    );
  }

  return (
    <div className={`card p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-warm-900 mb-4">
        📈 历年进面均分趋势
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ebe7e2" />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 12, fill: "#9b9184" }}
            tickFormatter={(v) => `${v}年`}
          />
          <YAxis
            domain={["dataMin - 5", "dataMax + 5"]}
            tick={{ fontSize: 11, fill: "#b8b0a5" }}
          />
          <Tooltip
            contentStyle={{
              borderRadius: "0.75rem",
              border: "1px solid #ebe7e2",
              boxShadow: "0 4px 16px rgba(0,0,0,0.06)",
              fontSize: "12px",
            }}
            formatter={(value: number) => [`${value.toFixed(1)} 分`, "平均进面分"]}
            labelFormatter={(label) => `${label} 年`}
          />
          <Line
            type="monotone"
            dataKey="avg_score"
            stroke="#1e6b4e"
            strokeWidth={2.5}
            dot={{ fill: "#1e6b4e", r: 4 }}
            activeDot={{ r: 6, fill: "#1e6b4e" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/analysis/TrendChart.tsx
git commit -m "feat: add TrendChart component with recharts line chart"
```

---

### Task 9: ResultPage 改造

**Files:**
- Modify: `frontend/src/pages/Analysis/ResultPage.tsx`

**Interfaces:**
- Consumes: `PositionCard`, `StatsOverview`, `TrendChart` components; updated `AnalysisResult` with difficulty fields
- Produces: 完整结果页含概览统计、难度排序岗位列表、趋势图

替换整个文件内容。关键改动：
1. 引入新组件
2. 顶部 StatsOverview + tier distribution
3. 用 PositionCard 替代内联 PositionCard
4. 底部 TrendChart（默认选用户首选城市）
5. 刷新时从 URL search params 重建请求

- [ ] **Step 1: Write new ResultPage**

```tsx
import { useEffect, useState, useMemo } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, BarChart3, RefreshCw } from "lucide-react";
import { analysisApi, type AnalysisResult, type TrendDataPoint, type StatsOverview as StatsOverviewType } from "../../services/api";
import PositionCard from "../../components/analysis/PositionCard";
import StatsOverview from "../../components/analysis/StatsOverview";
import TrendChart from "../../components/analysis/TrendChart";

// Simple spinner while loading
function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
    </div>
  );
}

export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [result, setResult] = useState<AnalysisResult | null>(
    (location.state as AnalysisResult) || null
  );
  const [stats, setStats] = useState<StatsOverviewType | null>(null);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(false);

  // If no result in state, try to reconstruct from URL params
  useEffect(() => {
    if (!result && searchParams.toString()) {
      setLoading(true);
      const params: Record<string, any> = {};
      const keys = ["birth_year","gender","education","degree","major","political_status","work_experience_years","preferred_cities","preferred_category","year"];
      keys.forEach(k => {
        const v = searchParams.get(k);
        if (v) {
          params[k] = k === "birth_year" || k === "work_experience_years" || k === "year" ? parseInt(v) : v;
        }
      });
      analysisApi.recommend(params)
        .then(setResult)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, []);

  // Fetch stats on mount
  useEffect(() => {
    analysisApi.getStats().then(setStats).catch(() => {});
  }, []);

  // Fetch trend for first recommended city
  useEffect(() => {
    if (result?.recommendations?.length) {
      const city = result.recommendations[0].city;
      analysisApi.getTrend(city).then((res) => setTrendData(res.data)).catch(() => {});
    }
  }, [result]);

  // Tier distribution
  const tierCounts = useMemo(() => {
    const counts: Record<string, number> = { "保底": 0, "稳妥": 0, "冲刺": 0 };
    result?.recommendations.forEach(p => {
      counts[p.tier] = (counts[p.tier] || 0) + 1;
    });
    return counts;
  }, [result]);

  if (loading) return <Spinner />;
  if (!result) {
    return (
      <div className="text-center py-20 space-y-4">
        <RefreshCw className="h-10 w-10 text-warm-300 mx-auto" />
        <p className="text-warm-500">未找到分析结果</p>
        <button onClick={() => navigate("/analysis")} className="btn-primary">去填写信息</button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back */}
      <button onClick={() => navigate("/analysis")} className="btn-ghost text-sm">
        <ArrowLeft className="h-4 w-4" /> 返回修改
      </button>

      {/* Title */}
      <div>
        <h1 className="page-heading flex items-center gap-2">
          🎯 岗位推荐结果
        </h1>
        <p className="text-sm text-warm-500 mt-1">{result.summary}</p>
      </div>

      {/* Stats overview */}
      <StatsOverview
        stats={stats}
        matchedCount={result.matched_positions}
        totalCount={result.total_positions}
        tierCounts={tierCounts}
      />

      {/* Recommendations header */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-warm-900 flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-brand-500" />
          推荐岗位 ({result.recommendations.length})
          <span className="text-xs text-warm-400 font-normal">
            按综合难度从易到难排列
          </span>
        </h2>
      </div>

      {/* Position cards */}
      <div className="space-y-4">
        {result.recommendations.map((pos) => (
          <PositionCard key={pos.id} pos={pos} />
        ))}
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <TrendChart data={trendData} />
      )}

      {/* Data source note */}
      <div className="card p-4 bg-warm-50/50 border-warm-200/50">
        <p className="text-xs text-warm-400 text-center">
          数据来源：湖南省人事考试网历年进面名单公示。分数为进面最低分/最高分/平均分，供参考。
          难度分综合进面分、竞争比、招录人数等多维度计算，数值越低越好考。
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Analysis/ResultPage.tsx
git commit -m "feat: overhaul ResultPage with difficulty scoring, stats overview, and trend chart"
```

---

### Task 10: FormPage URL 持久化

**Files:**
- Modify: `frontend/src/pages/Analysis/FormPage.tsx`

**Interfaces:**
- 提交时将表单参数写入 URL search params，使结果页刷新时能恢复

改动聚焦在 `handleSubmit` 函数和页面加载时从 URL 恢复表单。

- [ ] **Step 1: Modify FormPage**

In `FormPage.tsx`:

1. Add import: `import { useSearchParams } from "react-router-dom";`

2. Add at top of component:
```tsx
const [searchParams, setSearchParams] = useSearchParams();
```

3. Modify `handleSubmit` to set URL params:
```tsx
const handleSubmit = async () => {
  setLoading(true);
  try {
    const result = await analysisApi.recommend(form);
    // Persist form params to URL
    const params = new URLSearchParams();
    Object.entries(form).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== "") {
        params.set(k, String(v));
      }
    });
    setSearchParams(params, { replace: true });
    navigate("/analysis/result", { state: result });
  } catch (err) {
    console.error(err);
  } finally {
    setLoading(false);
  }
};
```

4. Add effect to restore form from URL on load (after the existing profile load effect):
```tsx
// Restore from URL params if present
useEffect(() => {
  if (searchParams.toString()) {
    const restored: Partial<ProfileRequest> = {};
    const strKeys = ["gender","education","degree","major","political_status","preferred_cities","preferred_category"];
    const numKeys = ["birth_year","work_experience_years","year"];
    strKeys.forEach(k => {
      const v = searchParams.get(k);
      if (v) (restored as any)[k] = v;
    });
    numKeys.forEach(k => {
      const v = searchParams.get(k);
      if (v) (restored as any)[k] = parseInt(v);
    });
    if (Object.keys(restored).length > 0) {
      setForm(prev => ({ ...prev, ...restored }));
    }
  }
}, []);
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Analysis/FormPage.tsx
git commit -m "feat: persist form params to URL for result page refresh resilience"
```

---

### Task 11: 端到端验证

**Files:**
- None (manual check)

- [ ] **Step 1: Start backend**

```bash
cd backend
python -c "import sys; sys.path.insert(0,'.'); import os; os.environ['DATABASE_URL']='sqlite:///hunan_exam.db'; from app.core.database import SessionLocal; from app.models.position import PositionHistory; db=SessionLocal(); print(f'{db.query(PositionHistory).count()} positions in DB'); db.close()"
```

If 0 positions, seed data:
```bash
cd backend && python scripts/seed_positions.py
```

Start server:
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Walk through the flow**

1. Open `http://localhost:5173/login` → login
2. Navigate to `/analysis` → fill form (pick 长沙 + 省市直)
3. Click "开始分析" → verify:
   - StatsOverview cards show
   - Position cards ordered by difficulty score (easiest first)
   - Each card shows difficulty ring with tier label
   - Expand card → see difficulty breakdown
   - Trend chart appears at bottom
4. Refresh result page → should reconstruct from URL params (no "未找到分析结果")
5. Change form back → navigate to `/analysis`, pick different city/category → verify different results
6. Check `/analysis` page loads and restores from URL params

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "chore: end-to-end verification fixes"
```
