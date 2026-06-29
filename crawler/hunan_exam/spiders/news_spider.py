"""
Spider for scraping Hunan current affairs and policy news.

Target sites:
  - hunan.gov.cn (湖南省政府门户)
  - hn.rednet.cn (红网)
  - hunan.voc.com.cn (华声在线)
  - hunan.people.com.cn (人民网湖南)

"""
import scrapy
from datetime import datetime
from hunan_exam.items import NewsArticleItem


class HunanGovSpider(scrapy.Spider):
    """Scrape Hunan provincial government official announcements."""

    name = "hunan_gov"
    allowed_domains = ["hunan.gov.cn"]
    start_urls = [
        "https://www.hunan.gov.cn/hnyw/zwdt/",         # 政务动态
        "https://www.hunan.gov.cn/topic/sxgf/zcjd/",   # 政策解读
    ]

    def parse(self, response):
        """Parse news list page."""
        articles = response.css("ul.list-news li, div.news-list a")
        for article in articles:
            link = article.css("a::attr(href)").get()
            title = article.css("a::attr(title)").get() or article.css("a::text").get()
            pub_date = article.css("span.date::text, span.time::text").get()

            if link and title:
                yield response.follow(
                    link,
                    self.parse_article,
                    meta={"title": title.strip(), "pub_date": pub_date.strip() if pub_date else ""},
                )

        # Pagination
        next_page = response.css("a.next::attr(href), a.page-next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        """Parse individual news article."""
        title = response.meta["title"]
        pub_date = response.meta.get("pub_date", "")

        # Extract main content
        content_parts = response.css(
            "div.article-content p::text, "
            "div.TRS_Editor p::text, "
            "div.news-content p::text"
        ).getall()
        content = "\n".join(p.strip() for p in content_parts if p.strip())

        if not content:
            return

        # Categorize
        category = self._categorize(title, content)

        item = NewsArticleItem(
            source_url=response.url,
            source_name="湖南省政府",
            title=title,
            content=content,
            publish_date=pub_date,
            category=category,
            tags=self._extract_tags(title, content),
        )
        yield item

    @staticmethod
    def _categorize(title: str, content: str) -> str:
        text = title + content[:200]
        if any(kw in text for kw in ["政策", "条例", "办法", "规定", "通知"]):
            return "政策"
        elif any(kw in text for kw in ["经济", "产业", "GDP", "企业", "园区"]):
            return "经济"
        elif any(kw in text for kw in ["民生", "教育", "医疗", "社保", "就业"]):
            return "社会"
        elif any(kw in text for kw in ["生态", "环境", "绿色", "污染"]):
            return "生态"
        elif any(kw in text for kw in ["三高四新", "乡村振兴", "长株潭"]):
            return "重要政策"
        return "综合"

    @staticmethod
    def _extract_tags(title: str, content: str) -> list[str]:
        """Extract keyword tags for metadata filtering."""
        keywords = [
            "三高四新", "乡村振兴", "长株潭一体化", "湘江新区",
            "自贸区", "数字经济", "营商环境", "基层治理",
            "共同富裕", "高质量发展", "绿色发展", "文旅融合",
        ]
        text = title + content[:500]
        return [kw for kw in keywords if kw in text]


class RedNetSpider(scrapy.Spider):
    """Scrape Hunan news from rednet.cn (红网)."""

    name = "rednet"
    allowed_domains = ["hn.rednet.cn", "www.rednet.cn"]

    start_urls = [
        "https://hn.rednet.cn/channel/56.html",  # 湖南频道
    ]

    def parse(self, response):
        """Parse rednet news list."""
        links = response.css("a[href*='/content/']::attr(href)").getall()
        for link in set(links):
            yield response.follow(link, self.parse_article)

        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_article(self, response):
        """Parse individual article."""
        title = response.css("h1::text").get()
        if not title:
            return

        content_parts = response.css("div.article-content p::text").getall()
        content = "\n".join(p.strip() for p in content_parts if p.strip())

        if len(content) < 200:  # Skip very short articles
            return

        item = NewsArticleItem(
            source_url=response.url,
            source_name="红网",
            title=title.strip(),
            content=content,
            publish_date="",
            category="综合",
            tags=[],
        )
        yield item
