"""
Pre-compute landing difficulty scores for all positions and save to JSON.

Run: cd backend && python scripts/precompute_difficulty.py [--year 2026]
"""

import json, sys, os, time, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.core.database import SessionLocal
from app.models.position import PositionHistory
from app.services.difficulty import (
    _normalize, get_tier,
    WEIGHT_ADMISSION, WEIGHT_COMPETITION, WEIGHT_ENROLLMENT, WEIGHT_TREND,
)

parser = argparse.ArgumentParser()
parser.add_argument("--year", type=int, default=None)
args = parser.parse_args()

db = SessionLocal()
t0 = time.time()

# Load positions
query = db.query(PositionHistory).filter(PositionHistory.is_active == True)
if args.year:
    query = query.filter(PositionHistory.year == args.year)
all_pos = query.all()
print(f"Loaded {len(all_pos)} positions in {time.time()-t0:.1f}s")

if not all_pos:
    print("No positions found!")
    db.close()
    exit(1)

# --- Phase 1: Collect all metrics (O(n), single pass) ---
t1 = time.time()

# Pre-compute category average ratios for fallback
cat_ratios: dict[str, list[float]] = {}
for pos in all_pos:
    a = getattr(pos, 'applicant_count', None)
    e = max(float(getattr(pos, 'enrollment_count', 1)), 1)
    cat = getattr(pos, 'exam_category', '')
    if a is not None and e > 0:
        cat_ratios.setdefault(cat, []).append(float(a) / e)

cat_avg_ratio: dict[str, float] = {}
for cat, rlist in cat_ratios.items():
    cat_avg_ratio[cat] = sum(rlist) / len(rlist) if rlist else 100.0
global_avg_ratio = sum(cat_avg_ratio.values()) / len(cat_avg_ratio) if cat_avg_ratio else 100.0

# Also pre-compute category average scores for fallback
cat_scores: dict[str, list[float]] = {}
for pos in all_pos:
    s = getattr(pos, 'min_score_interview', None)
    cat = getattr(pos, 'exam_category', '')
    if s is not None:
        cat_scores.setdefault(cat, []).append(float(s))
cat_avg_score: dict[str, float] = {}
for cat, slist in cat_scores.items():
    cat_avg_score[cat] = sum(slist) / len(slist) if slist else 130.0
global_avg_score = sum(cat_avg_score.values()) / len(cat_avg_score) if cat_avg_score else 130.0

scores = []
ratios = []
inv_enrolls = []

for pos in all_pos:
    # Score (O(1) lookup vs O(n) scan)
    s = getattr(pos, 'min_score_interview', None)
    if s is not None:
        scores.append(float(s))
    else:
        cat = getattr(pos, 'exam_category', '')
        scores.append(cat_avg_score.get(cat, global_avg_score))

    # Ratio (O(1) lookup vs O(n) scan)
    a = getattr(pos, 'applicant_count', None)
    e = max(float(getattr(pos, 'enrollment_count', 1)), 1)
    if a is not None and e > 0:
        ratios.append(float(a) / float(e))
    else:
        cat = getattr(pos, 'exam_category', '')
        ratios.append(cat_avg_ratio.get(cat, global_avg_ratio))

    inv_enrolls.append(1.0 / e)

min_score, max_score = min(scores), max(scores)
min_ratio, max_ratio = min(ratios), max(ratios)
min_inv, max_inv = min(inv_enrolls), max(inv_enrolls)
print(f"  Normalization ranges computed in {time.time()-t1:.1f}s")
print(f"  Scores: {min_score:.1f}-{max_score:.1f}, Ratios: {min_ratio:.1f}-{max_ratio:.1f}")
print(f"  Category avg ratios: { {k:round(v,1) for k,v in cat_avg_ratio.items()} }")

# --- Phase 2: Compute each position (O(n)) ---
t2 = time.time()
cache: dict[str, dict] = {}
for i, pos in enumerate(all_pos):
    admission = _normalize(scores[i], min_score, max_score)
    competition = _normalize(ratios[i], min_ratio, max_ratio)
    enrollment = _normalize(inv_enrolls[i], min_inv, max_inv)
    trend = 0.0

    total = (
        admission * WEIGHT_ADMISSION
        + competition * WEIGHT_COMPETITION
        + enrollment * WEIGHT_ENROLLMENT
        + trend * WEIGHT_TREND
    )
    total = max(0.0, min(100.0, total))

    cache[str(pos.id)] = {
        "score": round(total, 1),
        "tier": get_tier(total),
        "breakdown": {
            "admission_score": round(admission, 1),
            "competition_ratio": round(competition, 1),
            "enrollment_scale": round(enrollment, 1),
            "trend_adjustment": round(trend, 1),
            "total": round(total, 1),
        },
    }

print(f"  {len(cache)} scores computed in {time.time()-t2:.1f}s")

# --- Save ---
out_path = "difficulty_cache.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(cache, f, ensure_ascii=False)

size_kb = os.path.getsize(out_path) / 1024
print(f"Saved to {out_path} ({size_kb:.0f} KB)")

# Also write to Redis
try:
    from redis import Redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    redis_client.set("difficulty:cache", json.dumps(cache, ensure_ascii=False))
    print(f"Saved to Redis (difficulty:cache): {len(cache)} positions")
    redis_client.close()
except Exception as e:
    print(f"Warning: Failed to write to Redis: {e}")
db.close()
