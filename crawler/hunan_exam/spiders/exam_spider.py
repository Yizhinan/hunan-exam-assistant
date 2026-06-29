"""
Spider for scraping Hunan civil service exam questions.

Target sites (publicly accessible):
  - hunan.offcn.com (中公教育湖南 — 真题频道)
  - huatu.com (华图教育 — 湖南历年真题)
  - fenbi.com (粉笔 — 公开题库)

Respects robots.txt and uses polite download delays.
"""

import scrapy
from datetime import datetime

from hunan_exam.items import ExamQuestionItem


class OffcnExamSpider(scrapy.Spider):
    """Scrape Hunan exam questions from offcn.com (中公教育)."""

    name = "offcn_exam"
    allowed_domains = ["hunan.offcn.com", "www.offcn.com"]
    start_urls = [
        "https://hunan.offcn.com/html/hunangongwuyuan/kaoshitiku/xingce/moni/",
        "https://hunan.offcn.com/html/hunangongwuyuan/kaoshitiku/shenlun/",
    ]

    def parse(self, response):
        """Parse list page → follow detail links."""
        # List of article links pointing to individual question pages
        links = response.css("div.article-list ul li a::attr(href)").getall()
        for link in links:
            yield response.follow(link, self.parse_detail)

        # Pagination
        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_detail(self, response):
        """Parse a single exam question detail page."""
        title = response.css("h1::text").get() or ""
        content = response.css("div.article-content").get() or ""

        # Extract year and exam type from title
        year = self._extract_year(title)
        exam_type = "行测" if "行测" in title else "申论" if "申论" in title else "未知"
        module = self._extract_module(title)

        item = ExamQuestionItem(
            source_url=response.url,
            source_name="中公教育",
            exam_year=year,
            exam_type=exam_type,
            module=module,
            question_text=title,
            answer_text="",  # Parsed from detail content
            analysis_text="",
            raw_html=content,
        )
        yield item

    @staticmethod
    def _extract_year(title: str) -> int | None:
        import re
        m = re.search(r"(\d{4})", title)
        return int(m.group(1)) if m else None

    @staticmethod
    def _extract_module(title: str) -> str:
        modules = [
            "常识判断", "言语理解", "数量关系", "判断推理",
            "资料分析", "概括归纳", "综合分析", "提出对策",
            "贯彻执行", "文章写作",
        ]
        for m in modules:
            if m in title:
                return m
        return "其他"


class HuatuExamSpider(scrapy.Spider):
    """Scrape Hunan exam questions from huatu.com (华图教育)."""

    name = "huatu_exam"
    allowed_domains = ["www.huatu.com", "hunan.huatu.com"]

    start_urls = [
        "https://www.huatu.com/search/index?keyword=湖南公务员+真题",
    ]

    def parse(self, response):
        """Parse search results."""
        links = response.css("a[href*='/question/']::attr(href)").getall()
        for link in links:
            yield response.follow(link, self.parse_detail)

        # Pagination
        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_detail(self, response):
        """Parse individual question page."""
        question = response.css("div.question-stem::text").getall()
        answer = response.css("div.answer-content::text").getall()
        analysis = response.css("div.analysis::text").getall()

        item = ExamQuestionItem(
            source_url=response.url,
            source_name="华图教育",
            exam_year=None,
            exam_type="行测",
            module="",
            question_text="\n".join(q.strip() for q in question if q.strip()),
            answer_text="\n".join(a.strip() for a in answer if a.strip()),
            analysis_text="\n".join(a.strip() for a in analysis if a.strip()),
            raw_html=response.text,
        )
        yield item
