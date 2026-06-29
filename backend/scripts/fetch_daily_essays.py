"""
获取范文脚本 — 爬取 + AI 亮点分析 + 导入

用法:
  cd backend
  python scripts/fetch_daily_essays.py           # 爬取+分析+导入
  python scripts/fetch_daily_essays.py --dry-run # 仅爬取不分析
  python scripts/fetch_daily_essays.py --import-only  # 仅导入已有数据
"""

import sys
import json
import os
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.database import engine, Base, SessionLocal
from app.core.llm_client import chat_json  # Use DeepSeek for analysis

import app.models.user  # noqa
import app.models.document  # noqa
import app.models.essay  # noqa
import app.models.daily_essay  # noqa

settings = get_settings()

# ---- AI Analysis Prompt ----

ANALYSIS_PROMPT = """你是一位申论写作教学专家。请对以下申论范文进行专业分析。

## 分析要求

1. **亮点分析** (highlights)：从文章结构、论证方法、语言特色、论点深度等方面指出3-5个亮点
2. **要点提炼** (key_points)：提炼文章的核心观点、论证框架和可借鉴的写作技巧

## 输出格式（严格 JSON）

{
  "topic": "文章主题（如乡村振兴、基层治理等）",
  "highlights": "### 结构亮点\\n1. ...\\n2. ...\\n\\n### 论证技巧\\n1. ...\\n2. ...\\n\\n### 语言特色\\n1. ...\\n2. ...",
  "key_points": "### 核心论点\\n...\\n\\n### 论证框架\\n...\\n\\n### 可借鉴技巧\\n..."
}
"""


def analyze_essay(title: str, content: str) -> Optional[dict]:
    """Use DeepSeek to analyze an essay and extract highlights."""
    if not settings.DEEPSEEK_API_KEY:
        print("  [SKIP] 未配置 DEEPSEEK_API_KEY，跳过 AI 分析")
        return {"topic": "综合", "highlights": "", "key_points": ""}

    user_msg = f"## 文章标题\n{title}\n\n## 文章正文\n{content[:3000]}"

    try:
        result = chat_json(ANALYSIS_PROMPT, user_msg)
        return result
    except Exception as e:
        print(f"  [WARN] AI 分析失败: {e}")
        return {"topic": "综合", "highlights": "", "key_points": ""}


def import_essays(essays: list[dict], use_ai: bool = True):
    """Import essays into the daily_essays table."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    existing_dates = {
        row[0] for row in
        db.execute("SELECT recommend_date FROM daily_essays").fetchall()
    }

    today = date.today()
    imported = 0

    for i, essay in enumerate(essays):
        title = essay.get("title", "").strip()
        content = essay.get("content", "").strip()

        if not title or len(content) < 200:
            continue

        # Assign a date: start from today and work backwards for unfilled dates
        rec_date = today + timedelta(days=i)
        while rec_date in existing_dates:
            rec_date += timedelta(days=1)

        # AI analysis
        analysis = {}
        if use_ai:
            print(f"  分析: {title[:40]}...")
            analysis = analyze_essay(title, content)

        # Create record
        essay_record = __import__("app.models.daily_essay", fromlist=["DailyEssay"]).DailyEssay(
            title=title,
            content=content,
            topic=analysis.get("topic") or essay.get("topic") or "综合",
            source_name=essay.get("source_name", ""),
            source_url=essay.get("source_url", ""),
            recommend_date=rec_date,
            highlights=analysis.get("highlights", ""),
            key_points=analysis.get("key_points", ""),
        )

        db.add(essay_record)
        existing_dates.add(rec_date)
        imported += 1
        print(f"  [OK] {rec_date}: {title[:50]}")

    db.commit()
    db.close()
    print(f"\n导入完成! 共 {imported} 篇")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="获取并导入申论范文")
    parser.add_argument("--dry-run", action="store_true", help="仅爬取不分析不导入")
    parser.add_argument("--import-only", action="store_true", help="从 stdin 读取 JSON 直接导入")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 分析")
    args = parser.parse_args()

    if args.import_only:
        data = json.load(sys.stdin)
        import_essays(data, use_ai=not args.no_ai)
        return

    # Run spider
    import subprocess
    spider_dir = Path(__file__).resolve().parent.parent.parent / "crawler"
    print("爬取范文中...")

    essays = []
    for spider in ["people_essay", "qstheory_essay"]:
        result = subprocess.run(
            [sys.executable, "-m", "scrapy", "runspider",
             str(spider_dir / "hunan_exam" / "spiders" / "essay_spider.py"),
             "-a", f"name={spider}", "-o", "-", "-t", "json"],
            capture_output=True, text=True, timeout=120,
            cwd=str(spider_dir),
        )
        if result.stdout.strip():
            try:
                items = json.loads(result.stdout)
                essays.extend(items)
                print(f"  {spider}: {len(items)} 篇")
            except json.JSONDecodeError:
                print(f"  {spider}: 解析失败")

    if args.dry_run:
        print(f"\n爬取到 {len(essays)} 篇 (dry-run, 不导入)")
        if essays:
            print(json.dumps(essays[:3], ensure_ascii=False, indent=2))
        return

    if essays:
        import_essays(essays, use_ai=not args.no_ai)
    else:
        print("未爬取到新范文")


if __name__ == "__main__":
    main()
