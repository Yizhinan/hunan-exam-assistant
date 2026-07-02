"""
Spider for collecting high-quality model essays (申论范文).

Sources:
  - people.com.cn (人民网 — 观点/时评频道)
  - qstheory.cn (求是网 — 理论文章)
  - byteseu.com (半月谈 — 评论文章)

These are publicly accessible editorial/opinion pieces that serve as
excellent references for 申论 writing style and argumentation.
"""
import re
import scrapy
from datetime import date, datetime
from hunan_exam.items import EssayItem


class PeopleDailyEssaySpider(scrapy.Spider):
    """Crawl opinion/editorial pieces from 人民网 (people.com.cn)."""

    name = "people_essay"
    allowed_domains = ["people.com.cn", "opinion.people.com.cn"]
    start_urls = [
        "http://opinion.people.com.cn/GB/223228/index.html",  # 人民网观点频道
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
    }

    def parse(self, response):
        """Parse article list."""
        links = response.css("a::attr(href)").getall()
        for link in links:
            if any(kw in link for kw in ["opinion.people.com.cn/n1/", "paper.people.com.cn"]):
                yield response.follow(link, self.parse_article)

    def parse_article(self, response):
        """Extract article content."""
        title = response.css("h1::text, div.article h1::text, div.text_title h1::text").get()
        if not title:
            return

        # Extract main content
        content_parts = response.css(
            "div.article p::text, div.text_content p::text, div.box_con p::text"
        ).getall()
        content = "\n".join(p.strip() for p in content_parts if len(p.strip()) > 20)

        if len(content) < 300:
            return  # Skip very short pieces

        yield EssayItem(
            title=title.strip(),
            content=content,
            source_name="人民日报/人民网",
            source_url=response.url,
            topic=self._extract_topic(title + content[:200]),
        )

    @staticmethod
    def _extract_topic(text: str) -> str:
        topics = {
            "乡村振兴": ["乡村", "三农", "农村", "农业"],
            "基层治理": ["基层", "社区", "网格", "治理"],
            "经济发展": ["经济", "产业", "高质量发展", "新质生产力"],
            "文化自信": ["文化", "传统", "非遗", "文艺"],
            "生态文明": ["生态", "绿色", "环保", "低碳"],
            "科技创新": ["科技", "创新", "数字", "AI"],
            "民生保障": ["民生", "就业", "教育", "医疗", "养老"],
            "法治建设": ["法治", "法律", "司法", "执法"],
            "青年担当": ["青年", "青春", "奋斗", "时代"],
            "党的建设": ["党建", "党员", "干部", "作风"],
        }
        for topic, keywords in topics.items():
            if any(kw in text for kw in keywords):
                return topic
        return "时政综合"


class QstheorySpider(scrapy.Spider):
    """Crawl from 求是网 (qstheory.cn) — authoritative theory articles."""

    name = "qstheory_essay"
    allowed_domains = ["qstheory.cn", "www.qstheory.cn"]
    start_urls = [
        "http://www.qstheory.cn/llwx/",  # 理论文章
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "ROBOTSTXT_OBEY": True,
    }

    def parse(self, response):
        links = response.css("a::attr(href)").getall()
        for link in links:
            if "/202" in link and "qstheory.cn" in link:  # Articles from recent years
                yield response.follow(link, self.parse_article)

    def parse_article(self, response):
        title = response.css("h1::text, div.article-title::text").get()
        if not title:
            return

        content_parts = response.css(
            "div.article-content p::text, div.text p::text, div.TRS_Editor p::text"
        ).getall()
        content = "\n".join(p.strip() for p in content_parts if len(p.strip()) > 20)

        if len(content) < 300:
            return

        yield EssayItem(
            title=title.strip(),
            content=content,
            source_name="求是网",
            source_url=response.url,
            topic=PeopleDailyEssaySpider._extract_topic(title + content[:200]),
        )
