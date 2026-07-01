"""获取范文脚本 — LLM 智能抓取 + 分析 + 导入。

采用混合架构：
  1. requests + BeautifulSoup 发现文章链接（轻量级，无需 LLM）
  2. requests 获取文章页面 HTML
  3. DeepSeek LLM 从原始网页文本中智能提取范文正文（替代脆弱的 CSS 选择器）
  4. DeepSeek LLM 分析范文亮点和要点
  5. 异步写入数据库

用法:
  cd backend
  python scripts/fetch_daily_essays.py              # 抓取+分析+导入
  python scripts/fetch_daily_essays.py --dry-run     # 仅抓取不导入
  python scripts/fetch_daily_essays.py --no-ai       # 跳过 AI 分析
"""

import asyncio
import json
import logging
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.llm_client import chat, chat_json

logger = logging.getLogger(__name__)
settings = get_settings()

# ---- HTTP Session ----
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1.0,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

REQUEST_TIMEOUT = 30


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ---- Essay Sources (link discovery only) ----
ESSAY_SOURCES = [
    {
        "key": "people",
        "label": "人民网观点频道",
        "source_name": "人民日报/人民网",
        "list_urls": [
            "http://opinion.people.com.cn/GB/223228/index.html",
        ],
        "article_link_filter": lambda href: (
            href and "opinion.people.com.cn/n1/" in href
        ),
        "link_base": "http://opinion.people.com.cn",
    },
    {
        "key": "xinhua",
        "label": "新华网评论",
        "source_name": "新华网",
        "list_urls": [
            "http://www.xinhuanet.com/comments/",
            "http://www.news.cn/comments/",
        ],
        "article_link_filter": lambda href: (
            href and ("news.cn/" in href or "xinhuanet.com/" in href)
            and "/202" in href
            and any(kw in href for kw in ["/comments/", "/fortune/", "/politics/", "/culture/"])
        ),
        "link_base": None,
    },
    {
        "key": "qstheory",
        "label": "求是网理论文章",
        "source_name": "求是网",
        "list_urls": [
            "http://www.qstheory.cn/",
        ],
        "article_link_filter": lambda href: (
            href and "qstheory.cn/" in href and "/202" in href
        ),
        "link_base": None,
    },
]

# ---- LLM Prompts ----

EXTRACT_PROMPT = """你是一位专业的内容编辑。请从以下网页文本中提取出**申论范文/评论文章**的标题和正文。

网页文本是从 HTML 页面提取的，可能包含导航栏、广告、推荐链接等噪音内容。请识别并只提取主要的文章内容。

## 提取规则
1. **标题**：找出文章的正式标题（通常是最醒目的标题文字）
2. **正文**：提取完整的文章正文，去掉导航、页脚、广告、相关推荐等非正文内容
3. **主题标签**：根据文章内容判断话题类别

## 话题类别
乡村振兴 / 基层治理 / 经济发展 / 文化自信 / 生态文明 / 科技创新 / 民生保障 / 法治建设 / 青年担当 / 党的建设 / 时政综合

## 输出格式（严格 JSON）
{{
  "title": "文章标题",
  "content": "完整的文章正文（清理后的纯文本）",
  "topic": "话题类别",
  "is_valid_essay": true
}}

如果网页中没有找到有效的申论范文或评论文章（如纯新闻、图片集、视频页等），请设置 is_valid_essay 为 false。

## 网页文本
{page_text}
"""

ANALYSIS_PROMPT = """你是一位申论写作教学专家。请对以下申论范文进行专业分析与点评。

## 分析要求
1. **亮点分析** (highlights)：从文章结构、论证方法、语言特色、论点深度等方面指出3-5个亮点
2. **要点提炼** (key_points)：提炼文章的核心观点、论证框架和可借鉴的写作技巧

## 输出格式（严格 JSON）
{{
  "highlights": "### 结构亮点\\n1. ...\\n2. ...\\n\\n### 论证技巧\\n1. ...\\n2. ...\\n\\n### 语言特色\\n1. ...\\n2. ...",
  "key_points": "### 核心论点\\n...\\n\\n### 论证框架\\n...\\n\\n### 可借鉴技巧\\n1. ...\\n2. ...\\n3. ..."
}}

## 范文标题
{title}

## 范文正文
{content}
"""


# ============================================================
# Phase 1: Link discovery (lightweight, no LLM needed)
# ============================================================

def _discover_article_links(session: requests.Session, stats: dict) -> list[dict]:
    """Fetch list pages and discover article URLs from all sources."""
    all_links: list[dict] = []

    for src in ESSAY_SOURCES:
        logger.info(f"发现链接: {src['label']} ({src['key']})...")
        article_urls: set[str] = set()
        link_base = src.get("link_base")

        for list_url in src["list_urls"]:
            try:
                try:
                    resp = session.get(list_url, timeout=REQUEST_TIMEOUT)
                    resp.encoding = resp.apparent_encoding or "utf-8"
                except requests.SSLError:
                    logger.debug(f"    SSL 验证失败，跳过验证: {list_url}")
                    resp = session.get(list_url, timeout=REQUEST_TIMEOUT, verify=False)
                    resp.encoding = resp.apparent_encoding or "utf-8"
            except requests.RequestException as e:
                stats.setdefault("errors", []).append(f"{src['label']}: 列表页不可达 — {e}")
                logger.warning(f"    列表页 {list_url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                if not href:
                    continue
                if href.startswith("http"):
                    full_url = href
                elif link_base:
                    full_url = urljoin(link_base, href)
                else:
                    full_url = urljoin(list_url, href)

                if src["article_link_filter"](full_url):
                    article_urls.add(full_url)

        logger.info(f"    找到 {len(article_urls)} 个文章链接")

        # Limit to 8 most recent articles per source
        sorted_urls = sorted(article_urls, reverse=True)[:8]
        for url in sorted_urls:
            all_links.append({
                "url": url,
                "source_name": src["source_name"],
                "source_key": src["key"],
            })

    return all_links


# ============================================================
# Phase 2: Fetch page HTML → extract raw text
# ============================================================

def _fetch_page_text(session: requests.Session, url: str) -> str | None:
    """Fetch a web page and extract raw visible text (no LLM yet)."""
    try:
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except requests.SSLError:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
            resp.encoding = resp.apparent_encoding or "utf-8"
    except requests.RequestException as e:
        logger.debug(f"    请求失败 {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove obvious non-content elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header",
                               "iframe", "noscript", "form", "input", "button"]):
        tag.decompose()

    # Get all visible text
    text = soup.get_text(separator="\n", strip=True)

    # Clean up: remove excessive blank lines but keep paragraph structure
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cleaned = "\n".join(lines)

    if len(cleaned) < 200:
        logger.debug(f"    页面内容过短 ({len(cleaned)} chars): {url}")
        return None

    return cleaned


# ============================================================
# Phase 3: LLM extracts essay content from page text
# ============================================================

def _llm_extract_essay(page_text: str, source_name: str, url: str) -> dict | None:
    """Use LLM to intelligently extract essay content from raw page text."""
    if not settings.DEEPSEEK_API_KEY:
        return None

    # Truncate to avoid token limits
    prompt = EXTRACT_PROMPT.format(page_text=page_text[:8000])

    try:
        result = chat_json(
            system_prompt="你是一位专业的内容编辑，擅长从网页文本中提取文章正文。",
            user_message=prompt,
            temperature=0.1,
        )
        if not result.get("is_valid_essay"):
            logger.debug(f"    LLM 判定非范文: {url}")
            return None

        title = (result.get("title") or "").strip()
        content = (result.get("content") or "").strip()
        topic = (result.get("topic") or "时政综合").strip()

        if not title or len(content) < 300:
            logger.debug(f"    LLM 提取内容不足: title={bool(title)}, content_len={len(content)}")
            return None

        return {
            "title": title,
            "content": content,
            "topic": topic,
            "source_name": source_name,
            "source_url": url,
        }
    except Exception as e:
        logger.warning(f"    LLM 提取失败: {e}")
        return None


# ============================================================
# Phase 4: LLM analysis (highlights + key points)
# ============================================================

def _llm_analyze_essay(title: str, content: str) -> dict:
    """Use LLM to analyze essay structure, technique, and language."""
    if not settings.DEEPSEEK_API_KEY:
        return {"highlights": "", "key_points": ""}

    prompt = ANALYSIS_PROMPT.format(title=title, content=content[:3000])

    try:
        result = chat_json(
            system_prompt="你是一位申论写作教学专家，擅长分析文章结构和写作技巧。",
            user_message=prompt,
            temperature=0.2,
        )
        return {
            "highlights": result.get("highlights") or "",
            "key_points": result.get("key_points") or "",
        }
    except Exception as e:
        logger.warning(f"    LLM 分析失败: {e}")
        return {"highlights": "", "key_points": ""}


# ============================================================
# Phase 5: Import into database (async)
# ============================================================

async def _import_essays_async(essays: list[dict], use_ai: bool = True) -> tuple[int, int, int]:
    """Import essays into daily_essays table using async DB session."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text as sa_text
    from app.core.database import Base
    from app.models.daily_essay import DailyEssay

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        result = await db.execute(sa_text("SELECT title FROM daily_essays"))
        existing_titles: set[str] = {row[0] for row in result.fetchall()}

        today = date.today()
        imported = 0
        skipped = 0
        analyzed = 0

        for essay in essays:
            title = (essay.get("title") or "").strip()
            content = (essay.get("content") or "").strip()

            if not title or len(content) < 200:
                skipped += 1
                continue

            if title in existing_titles:
                skipped += 1
                continue

            topic = essay.get("topic") or "时政综合"
            highlights = ""
            key_points = ""

            if use_ai:
                try:
                    analysis = await asyncio.to_thread(
                        _llm_analyze_essay, title, content
                    )
                    if analysis:
                        highlights = analysis.get("highlights") or ""
                        key_points = analysis.get("key_points") or ""
                        analyzed += 1
                except Exception as e:
                    logger.warning(f"AI 分析失败 '{title[:30]}': {e}")

            # Assign to categories evenly
            exam_category = _classify_category(title, content, topic)

            rec_date = today
            inserted = False
            for _ in range(30):
                try:
                    record = DailyEssay(
                        title=title,
                        content=content,
                        topic=topic,
                        source_name=essay.get("source_name", ""),
                        source_url=essay.get("source_url", ""),
                        exam_category=exam_category,
                        recommend_date=rec_date,
                        highlights=highlights,
                        key_points=key_points,
                    )
                    db.add(record)
                    await db.flush()
                    await db.commit()

                    existing_titles.add(title)
                    imported += 1
                    logger.info(f"  [OK] {rec_date} [{exam_category}]: {title[:60]}")
                    inserted = True
                    break
                except Exception:
                    await db.rollback()
                    rec_date += timedelta(days=1)

            if not inserted:
                skipped += 1
                logger.warning(f"  [SKIP] {title[:30]}: 无法导入")

    await engine.dispose()
    logger.info(f"导入完成! 新增 {imported} 篇, 跳过 {skipped} 篇, AI分析 {analyzed} 篇")
    return imported, skipped, analyzed


def _classify_category(title: str, content: str, topic: str) -> str:
    """Classify essay into exam category based on content analysis."""
    text = title + content[:500]
    # 基层治理、乡村振兴 → 县乡基层
    if any(kw in text for kw in ["乡镇", "基层", "乡村", "农村", "社区", "街道", "脱贫攻坚"]):
        return "县乡基层"
    # 法治、执法、公安 → 行政执法
    if any(kw in text for kw in ["执法", "法治", "公安", "司法", "监管", "检察", "法院"]):
        return "行政执法"
    # Everything else → 省市直
    return "省市直"


# ============================================================
# Main orchestrator (async — called from FastAPI)
# ============================================================

async def refresh_essays_async(use_ai: bool = True, count: int = 9) -> dict:
    """
    从互联网抓取真实申论范文 → LLM 智能提取正文 → LLM 分析 → 导入数据库。

    流程：
      1. 从人民网/新华网/求是网发现文章链接
      2. 获取每篇文章的 HTML 页面
      3. LLM 从页面文本中智能提取范文正文（替代脆弱的 CSS 选择器）
      4. LLM 分析范文亮点和要点
      5. 异步写入数据库
    """
    stats: dict = {
        "status": "empty",
        "total_scraped": 0,
        "imported": 0,
        "skipped": 0,
        "analyzed": 0,
        "errors": [],
    }

    if not settings.DEEPSEEK_API_KEY:
        stats["errors"].append("未配置 DEEPSEEK_API_KEY，无法使用 LLM 提取范文")
        stats["status"] = "empty"
        return stats

    session = _make_session()

    # Phase 1: Discover article links
    logger.info("=" * 50)
    logger.info("Phase 1: 发现文章链接...")
    links = await asyncio.to_thread(_discover_article_links, session, stats)
    logger.info(f"共发现 {len(links)} 篇文章链接")

    if not links:
        stats["errors"].append("未发现任何文章链接（网站可能改版或网络不可达）")
        return stats

    # Limit to requested count
    links = links[:count]

    # Phase 2 & 3: Fetch each page → extract text → LLM extracts essay
    logger.info("=" * 50)
    logger.info("Phase 2-3: 获取页面 → LLM 提取范文正文...")
    essays = []
    for i, link in enumerate(links):
        url = link["url"]
        source_name = link["source_name"]
        logger.info(f"[{i+1}/{len(links)}] {url[:80]}...")

        # Fetch page text
        page_text = await asyncio.to_thread(_fetch_page_text, session, url)
        if not page_text:
            stats["errors"].append(f"页面获取失败: {url[:60]}")
            continue

        # LLM extracts essay from page text
        extracted = await asyncio.to_thread(
            _llm_extract_essay, page_text, source_name, url
        )
        if extracted:
            essays.append(extracted)
            logger.info(f"  ✓ {extracted['title'][:60]} [{extracted['topic']}]")
        else:
            logger.info(f"  ✗ 未提取到有效范文")

    stats["total_scraped"] = len(essays)
    if not essays:
        stats["errors"].append("LLM 未能从任何页面提取到有效范文")
        stats["status"] = "empty"
        return stats

    # Phase 4 & 5: Import with analysis
    logger.info("=" * 50)
    logger.info(f"Phase 4-5: 导入 {len(essays)} 篇范文...")
    imported, skipped, analyzed = await _import_essays_async(essays, use_ai=use_ai)
    stats["imported"] = imported
    stats["skipped"] = skipped
    stats["analyzed"] = analyzed
    stats["status"] = "ok" if imported > 0 else "partial"

    return stats


# ============================================================
# Sync wrapper (for CLI usage)
# ============================================================

def refresh_essays(use_ai: bool = True, count: int = 9) -> dict:
    """同步包装器 — CLI 使用。"""
    return asyncio.run(refresh_essays_async(use_ai=use_ai, count=count))


# ============================================================
# CLI entry point
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM 智能抓取并导入申论范文")
    parser.add_argument("--dry-run", action="store_true", help="仅抓取不导入")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 分析")
    parser.add_argument("--count", type=int, default=6, help="最多抓取篇数（默认6篇）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.dry_run:
        stats: dict = {
            "status": "empty", "total_scraped": 0,
            "imported": 0, "skipped": 0, "analyzed": 0, "errors": [],
        }
        session = _make_session()
        links = _discover_article_links(session, stats)[:args.count]
        print(f"\n发现 {len(links)} 篇文章链接 (dry-run)")
        for link in links[:5]:
            print(f"  {link['source_name']}: {link['url'][:80]}")
        if stats["errors"]:
            print("\n错误:")
            for err in stats["errors"]:
                print(f"  ✗ {err}")
        return

    result = refresh_essays(use_ai=not args.no_ai, count=args.count)
    print(f"\n=== LLM 智能抓取结果 ===")
    print(f"  状态:       {result['status']}")
    print(f"  成功提取:   {result['total_scraped']}")
    print(f"  新导入:     {result['imported']}")
    print(f"  AI 分析:    {result['analyzed']}")
    print(f"  跳过:       {result['skipped']}")
    if result["errors"]:
        print(f"  错误:")
        for err in result["errors"]:
            print(f"    ✗ {err}")


if __name__ == "__main__":
    main()
