"""
Scrape applicant counts from 湖南人事考试网 and update the database.

数据来源: 湖南人事考试网 (https://rsks.hunanpea.com/)
- 报名期间 (通常每年1月底-2月初) 每天上午公布各岗位报名缴费人数
- 最后公布时间: 报名最后一天下午 (2026年为2月2日下午)
- 公布报名人数较少的职位: 报名结束后第二天上午

Usage:
    cd backend
    python scripts/scrape_applicants.py --year 2026

Matching strategy (position_code is NULL for all positions):
    1. Exact match on department (单位名称) + position_name (岗位名称)
    2. Fuzzy match on department name (remove "湖南省" prefix, etc.)
    3. Match on department + city

Requirements:
    pip install requests beautifulsoup4
"""

import argparse
import logging
import re
import sys
import time
from typing import Optional

import requests
from sqlalchemy import update
from sqlalchemy.orm import Session

# Add backend to path
sys.path.insert(0, "..")

from app.core.database import SessionLocal
from app.models.position import PositionHistory

logger = logging.getLogger(__name__)

# ============================================================
# Known data sources for Hunan exam registration statistics
# ============================================================

# 湖南人事考试网 — 公务员考试报名系统
HUNAN_EXAM_BASE = "https://rsks.hunanpea.com"

# 职位报名人数查询接口 (常见的几种可能路径)
# Actual endpoints may vary year to year — try each in order
QUERY_ENDPOINTS = [
    # 报名系统职位查询 (most common)
    f"{HUNAN_EXAM_BASE}/GwyExam/Position/PositionList",
    f"{HUNAN_EXAM_BASE}/GwyExamSignUp/Position/PositionList",
    # 各市州分站
    f"{HUNAN_EXAM_BASE}/Index.do",
]

# 红星网 — 备用数据源
HONGXING_BASE = "https://www.hxw.gov.cn"

# ============================================================
# Page scraping
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def fetch_position_list_page(year: int, page: int = 1, page_size: int = 100) -> Optional[str]:
    """Fetch one page of position data from the exam registration system."""
    session = requests.Session()
    session.headers.update(HEADERS)

    # Try each known endpoint
    for endpoint in QUERY_ENDPOINTS:
        try:
            params = {
                "year": year,
                "page": page,
                "pageSize": page_size,
                "examType": "公务员",
            }
            resp = session.get(endpoint, params=params, timeout=30)
            if resp.status_code == 200 and len(resp.text) > 500:
                logger.info(f"Got response from {endpoint}: {len(resp.text)} bytes")
                return resp.text
            else:
                logger.debug(f"{endpoint}: status={resp.status_code}, len={len(resp.text)}")
        except requests.RequestException as e:
            logger.debug(f"{endpoint}: {e}")
            continue

    logger.warning(f"All endpoints failed for year={year} page={page}")
    return None


# ============================================================
# HTML Parsing
# ============================================================

def parse_position_table(html: str) -> list[dict]:
    """Parse position data from HTML table.

    Expected columns: 单位名称, 职位名称, 职位代码, 招录人数, 报名人数, ...
    Returns list of dicts with keys: department, position_name, position_code,
                                     enrollment_count, applicant_count
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Try to find a data table
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Detect header row
        header_row = rows[0]
        headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

        # Map column names to indices
        col_map = {}
        for i, h in enumerate(headers):
            h_lower = h.lower()
            if any(kw in h for kw in ["单位", "部门", "用人单位"]):
                col_map["department"] = i
            elif any(kw in h for kw in ["职位", "岗位", "招录职位"]):
                col_map["position_name"] = i
            elif any(kw in h for kw in ["职位代码", "岗位代码"]):
                col_map["position_code"] = i
            elif any(kw in h for kw in ["招录", "录用人数", "计划数"]):
                col_map["enrollment_count"] = i
            elif any(kw in h for kw in ["报名", "缴费", "报考"]):
                col_map["applicant_count"] = i

        # If we found at least department and applicant columns, parse data rows
        if "department" in col_map and "applicant_count" in col_map:
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < max(col_map.values()) + 1:
                    continue

                try:
                    dept = cells[col_map["department"]].get_text(strip=True)
                    pos_name = cells[col_map.get("position_name", 0)].get_text(strip=True) if "position_name" in col_map else ""
                    pos_code = cells[col_map["position_code"]].get_text(strip=True) if "position_code" in col_map else None
                    enroll = cells[col_map.get("enrollment_count", 0)].get_text(strip=True) if "enrollment_count" in col_map else "1"
                    applicants = cells[col_map["applicant_count"]].get_text(strip=True)

                    # Clean up numbers
                    applicants = re.sub(r"[^\d]", "", applicants)
                    enroll = re.sub(r"[^\d]", "", enroll)

                    if applicants:
                        results.append({
                            "department": dept,
                            "position_name": pos_name,
                            "position_code": pos_code,
                            "enrollment_count": int(enroll) if enroll else 1,
                            "applicant_count": int(applicants),
                        })
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse row: {e}")
                    continue

            break  # Use first matching table

    return results


# ============================================================
# Fallback: Manual data entry from published statistics
# ============================================================

# 2026省考报名统计 — 来自新闻报道
# 报名期间每天上午9时公布数据
# 最终数据: 2月2日下午 (最后一次公布)
#
# 如果网站已关闭报名系统入口，可手动填入以下来源的数据:
# - 湖南人事考试网发布的PDF/Excel报名统计表
# - 各培训机构(华图/中公/粉笔)整理的报名数据
# - 新闻报道中的汇总数据
#
# Format: dict[position_code_or_key, applicant_count]

FALLBACK_DATA_2026: dict[str, int] = {
    # 填入已知的报名人数数据
    # "<position_code>": <applicant_count>,
}

# ============================================================
# Database update
# ============================================================

def find_matching_position(
    db: Session,
    scraped: dict,
    year: int,
) -> Optional[PositionHistory]:
    """Find the database position that matches a scraped row."""

    # Strategy 1: position_code exact match
    if scraped.get("position_code"):
        match = db.query(PositionHistory).filter(
            PositionHistory.year == year,
            PositionHistory.position_code == scraped["position_code"],
            PositionHistory.is_active == True,
        ).first()
        if match:
            return match

    # Strategy 2: department (normalized) + position_name exact match
    dept = scraped["department"].strip()
    pos_name = scraped.get("position_name", "").strip()

    # Normalize department name: remove province prefix
    dept_normalized = re.sub(r"^湖南省", "", dept)

    if pos_name:
        match = db.query(PositionHistory).filter(
            PositionHistory.year == year,
            PositionHistory.department == dept,
            PositionHistory.position_name == pos_name,
            PositionHistory.is_active == True,
        ).first()
        if match:
            return match

        # Try normalized
        match = db.query(PositionHistory).filter(
            PositionHistory.year == year,
            PositionHistory.department == dept_normalized,
            PositionHistory.position_name == pos_name,
            PositionHistory.is_active == True,
        ).first()
        if match:
            return match

    # Strategy 3: department contains match
    matches = db.query(PositionHistory).filter(
        PositionHistory.year == year,
        PositionHistory.department.contains(dept_normalized),
        PositionHistory.is_active == True,
    ).all()

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1 and pos_name:
        for m in matches:
            if m.position_name == pos_name:
                return m

    return None


def update_applicant_counts(
    db: Session,
    scraped_data: list[dict],
    year: int,
    dry_run: bool = False,
) -> dict:
    """Update applicant_count in the database from scraped data."""
    stats = {"total_scraped": len(scraped_data), "matched": 0, "updated": 0, "unmatched": 0}

    for row in scraped_data:
        pos = find_matching_position(db, row, year)
        if pos:
            stats["matched"] += 1
            if not dry_run:
                pos.applicant_count = row["applicant_count"]
                stats["updated"] += 1
            logger.debug(f"  ✓ {pos.department} | {pos.position_name} → {row['applicant_count']}")
        else:
            stats["unmatched"] += 1
            logger.debug(f"  ✗ No match: {row.get('department', '?')} | {row.get('position_name', '?')}")

    if not dry_run and stats["updated"] > 0:
        db.commit()
        logger.info(f"Committed {stats['updated']} updates")

    return stats


# ============================================================
# Main entry point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Scrape Hunan exam applicant counts")
    parser.add_argument("--year", type=int, default=2026, help="Exam year (default: 2026)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape but don't update DB")
    parser.add_argument("--use-fallback", action="store_true", help="Use hardcoded fallback data")
    parser.add_argument("--page-size", type=int, default=500, help="Page size for scraping")
    parser.add_argument("--max-pages", type=int, default=20, help="Max pages to fetch")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = parser.parse_args()

    db = SessionLocal()
    scraped_all: list[dict] = []

    try:
        if args.use_fallback:
            logger.info(f"Using fallback data for year {args.year}")
            fallback = FALLBACK_DATA_2026 if args.year == 2026 else {}
            for code, count in fallback.items():
                scraped_all.append({
                    "department": "",
                    "position_name": "",
                    "position_code": code,
                    "applicant_count": count,
                })
        else:
            logger.info(f"Scraping year {args.year} from 湖南人事考试网...")
            for page in range(1, args.max_pages + 1):
                logger.info(f"Fetching page {page}...")
                html = fetch_position_list_page(args.year, page, args.page_size)
                if not html:
                    logger.info("No more pages or endpoint unavailable")
                    break

                results = parse_position_table(html)
                if not results:
                    logger.info(f"Page {page}: no results found in HTML")
                    break

                logger.info(f"Page {page}: parsed {len(results)} positions")
                scraped_all.extend(results)

                if len(results) < args.page_size:
                    break  # Last page

                time.sleep(1)  # Be polite

        if not scraped_all:
            logger.warning(
                "No applicant data scraped. This is expected if:\n"
                "  1. Registration period is over and the query system is closed\n"
                "  2. The website structure has changed\n"
                "  3. Network access is restricted\n\n"
                "Try running during registration period (late January - early February).\n"
                "Alternatively, use --use-fallback with manually entered data."
            )
            return

        logger.info(f"Total scraped: {len(scraped_all)} positions")

        # Update database
        stats = update_applicant_counts(db, scraped_all, args.year, dry_run=args.dry_run)

        print("\n=== Results ===")
        print(f"  Scraped positions:   {stats['total_scraped']}")
        print(f"  Matched in DB:       {stats['matched']}")
        print(f"  Updated:             {stats['updated']}")
        print(f"  Unmatched:           {stats['unmatched']}")
        if args.dry_run:
            print("  (DRY RUN — no changes made)")

        # Verify
        if not args.dry_run and stats["updated"] > 0:
            from sqlalchemy import func
            total_with = db.query(func.count()).filter(
                PositionHistory.year == args.year,
                PositionHistory.is_active == True,
                PositionHistory.applicant_count.isnot(None),
            ).scalar()
            print(f"\n  DB positions with applicant count: {total_with}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
