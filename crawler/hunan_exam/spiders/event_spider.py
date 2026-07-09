"""
Spider for scraping national current events for exam prep.

Target sites:
  - xinhuanet.com/politics (新华网时政)
  - politics.people.com.cn (人民网时政)
"""

import re
from datetime import datetime

import scrapy
from hunan_exam.items import EventItem


class XinhuaPoliticsSpider(scrapy.Spider):
    """Scrape national politics/current-affairs news from 新华网."""

    name = "national_events"
    allowed_domains = ["xinhuanet.com", "www.xinhuanet.com", "news.cn", "www.news.cn"]
    start_urls = [
        "https://www.news.cn/politics/",
        "https://www.xinhuanet.com/politics/",
    ]

    def parse(self, response):
        """Parse news list page."""
        # xinhuanet/ news.cn uses various link patterns
        links = response.css(
            "a[href*='/2026']::attr(href), "
            "a[href*='/2025']::attr(href), "
            "a[href*='politics']::attr(href)"
        ).getall()

        for link in set(links):
            if not link.startswith("http"):
                if link.startswith("//"):
                    link = "https:" + link
                elif link.startswith("/"):
                    link = response.urljoin(link)
                else:
                    continue
            yield scrapy.Request(link, self.parse_article)

    def parse_article(self, response):
        """Parse individual news article."""
        title = response.css("h1::text, .title::text, .article-title::text").get()
        if not title:
            return
        title = title.strip()
        if len(title) < 10:
            return

        # Extract date from URL or page
        date_str = self._extract_date(response)

        # Extract content
        content_parts = response.css(
            "div.article-content p::text, "
            "div.article p::text, "
            "#detail-content p::text, "
            "div.detail-content p::text, "
            "div.news-content p::text"
        ).getall()
        content = "\n".join(p.strip() for p in content_parts if len(p.strip()) > 20)

        if len(content) < 500:
            return

        # Source name detection
        source_name = "新华网"
        source_el = response.css(".source::text, .info::text, .article-source::text").get()
        if source_el:
            source_name = source_el.strip()

        item = EventItem(
            source_url=response.url,
            source_name=source_name,
            title=title,
            content=content,
            event_date=date_str,
        )
        yield item

    @staticmethod
    def _extract_date(response) -> str:
        """Extract publish date from article page."""
        # Try meta tags
        for meta in response.css("meta[name='publishdate']::attr(content), meta[property='article:published_time']::attr(content)").getall():
            try:
                return datetime.fromisoformat(meta.replace("Z", "+00:00")[:10]).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass

        # Try visible date elements
        date_text = response.css(
            ".date::text, .time::text, .article-time::text, "
            ".info span::text, .source span::text"
        ).get()
        if date_text:
            match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", date_text)
            if match:
                return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"

        # Try URL date pattern
        url_match = re.search(r"/(\d{4})[-/](\d{2})[-/](\d{2})", response.url)
        if url_match:
            return f"{url_match.group(1)}-{url_match.group(2)}-{url_match.group(3)}"

        # Default: today
        return datetime.now().strftime("%Y-%m-%d")


class PeoplePoliticsSpider(scrapy.Spider):
    """Scrape national current-affairs news from 人民网时政频道."""

    name = "people_politics"
    allowed_domains = ["people.com.cn", "politics.people.com.cn", "www.people.com.cn"]
    start_urls = [
        "http://politics.people.com.cn/GB/1024/",
        "http://politics.people.com.cn/GB/8198/",
    ]

    def parse(self, response):
        """Parse news list page."""
        links = response.css("a::attr(href)").getall()
        for link in set(links):
            if not link.startswith("http"):
                if link.startswith("//"):
                    link = "https:" + link
                elif link.startswith("/"):
                    link = response.urljoin(link)
                else:
                    continue
            if "politics.people.com.cn" in link or "cpc.people.com.cn" in link:
                yield scrapy.Request(link, self.parse_article)

    def parse_article(self, response):
        """Parse individual article."""
        title = response.css("h1::text, .title::text").get()
        if not title:
            return
        title = title.strip()
        if len(title) < 10:
            return

        date_str = self._extract_date(response)

        content_parts = response.css(
            "div.box_con p::text, "
            "div.article-content p::text, "
            "div.text p::text"
        ).getall()
        content = "\n".join(p.strip() for p in content_parts if len(p.strip()) > 20)

        if len(content) < 500:
            return

        source_name = "人民网"
        source_el = response.css(".source::text").get()
        if source_el:
            source_name = source_el.strip().split()[0]

        item = EventItem(
            source_url=response.url,
            source_name=source_name,
            title=title,
            content=content,
            event_date=date_str,
        )
        yield item

    @staticmethod
    def _extract_date(response) -> str:
        """Extract publish date from article page."""
        date_text = response.css(".date::text, .time::text").get()
        if date_text:
            match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", date_text)
            if match:
                return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"

        url_match = re.search(r"/(\d{4})[-/](\d{2})[-/](\d{2})", response.url)
        if url_match:
            return f"{url_match.group(1)}-{url_match.group(2)}-{url_match.group(3)}"

        return datetime.now().strftime("%Y-%m-%d")
