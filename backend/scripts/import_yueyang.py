"""
从岳阳市红星网获取的2026年省考进面数据导入脚本。

数据来源：
  - 岳阳市2026年考试录用公务员集中面试公告（面试入围名单）
  - 岳阳市2026年考试录用公务员综合成绩及入围体检人员名单公告

运行: cd backend && python scripts/import_yueyang.py
"""

import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.core.database import engine, Base, SessionLocal
from app.models.position import PositionHistory

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Load merged data
data_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'yy_merged.json')
with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Loaded {len(data)} positions from {data_path}")

# Category classification rules
def classify_category(department: str, position_name: str) -> str:
    """Infer exam category from department and position name."""
    dept = department
    pos = position_name

    # 县乡基层: 乡镇/街道 positions
    township_keywords = ['乡镇', '街道', '镇', '乡']
    if any(k in dept or k in pos for k in township_keywords):
        return "县乡基层"

    # 行政执法: 公安/法院/检察院/司法/监狱/戒毒/城管/市场监管/应急/生态/执纪执法
    enforcement_keywords = [
        '公安', '法院', '检察', '司法', '监狱', '戒毒', '交警',
        '城管', '市场监督', '市场监管', '应急', '生态', '环境执法', '文化市场',
        '交通运输执法', '农业执法', '卫生健康执法', '应急管理',
        '巡特警', '特警', '看守所', '拘留所',
        '执纪执法', '监督执纪', '行政执法', '综合执法', '执法勤务',
        '纪委', '监委',
    ]
    if any(k in dept or k in pos for k in enforcement_keywords):
        return "行政执法"

    # Default: 省市直
    return "省市直"


def infer_education(dept: str, pos_name: str) -> str:
    """Infer education requirement (conservative default)."""
    # Most 岳阳市直 positions require 本科及以上
    if classify_category(dept, pos_name) == "县乡基层":
        # Township positions often accept 大专
        return "大专及以上"
    return "本科及以上"


def infer_degree(education: str) -> str:
    if "大专" in education and "本科" not in education:
        return "无要求"
    return "学士"


def infer_gender(pos_name: str) -> str:
    """Detect gender-restricted positions."""
    if '男' in pos_name and '女' not in pos_name:
        return "男性"
    if '女' in pos_name and '男' not in pos_name:
        return "女性"
    return "不限"


# Check existing 岳阳 data
existing_count = db.query(PositionHistory).filter(
    PositionHistory.city == "岳阳",
    PositionHistory.year == 2026,
).count()

if existing_count > 0:
    print(f"Deleting {existing_count} existing 岳阳 2026 positions...")
    db.query(PositionHistory).filter(
        PositionHistory.city == "岳阳",
        PositionHistory.year == 2026,
    ).delete()
    db.commit()

# Import
imported = 0
skipped = 0

for key_str, info in data.items():
    dept = info['department']
    pos_name = info['position_name']
    category = classify_category(dept, pos_name)
    edu = infer_education(dept, pos_name)
    degree = infer_degree(edu)
    gender = infer_gender(pos_name)

    pos = PositionHistory(
        year=2026,
        province="湖南",
        city="岳阳",
        district=None,
        department=dept,
        position_name=pos_name,
        exam_category=category,
        education_requirement=edu,
        degree_requirement=degree,
        major_requirement=None,  # 无法从面试名单获取专业要求
        political_requirement="不限",
        gender_requirement=gender,
        experience_requirement="不限",
        age_limit="35周岁以下",
        enrollment_count=info.get('enrollment_count', 1),
        applicant_count=None,  # 面试名单无法得知真实报名人数
        min_score_interview=round(info['min_written_score'], 2),
        max_score_interview=round(info.get('max_written_score', info['min_written_score']), 2),
        avg_score_interview=round(info.get('avg_written_score', info['min_written_score']), 2),
        interview_ratio="1:2",
        source="岳阳红星网",
        is_active=True,
    )
    db.add(pos)
    imported += 1

db.commit()
print(f"Imported {imported} positions for 岳阳市 2026 (skipped {skipped})")

# Verify
count = db.query(PositionHistory).filter(
    PositionHistory.city == "岳阳",
    PositionHistory.year == 2026,
).count()
by_cat = {}
for row in db.query(
    PositionHistory.exam_category,
    __import__('sqlalchemy').func.count(PositionHistory.id)
).filter(
    PositionHistory.city == "岳阳",
    PositionHistory.year == 2026,
).group_by(PositionHistory.exam_category).all():
    by_cat[row[0]] = row[1]

print(f"Verified: {count} 岳阳 2026 positions in DB")
for cat, cnt in by_cat.items():
    print(f"  {cat}: {cnt}")

db.close()
print("Done.")
