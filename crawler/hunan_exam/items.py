"""Scrapy Item definitions for exam questions and news articles."""

import scrapy


class ExamQuestionItem(scrapy.Item):
    """An exam question scraped from public exam-prep websites."""

    source_url = scrapy.Field()
    source_name = scrapy.Field()
    exam_year = scrapy.Field()
    exam_type = scrapy.Field()       # 行测 / 申论
    module = scrapy.Field()          # 常识判断 / 数量关系 / 申论-概括归纳 etc.
    question_text = scrapy.Field()
    answer_text = scrapy.Field()
    analysis_text = scrapy.Field()
    raw_html = scrapy.Field()


class NewsArticleItem(scrapy.Item):
    """A Hunan-related current affairs article."""

    source_url = scrapy.Field()
    source_name = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    publish_date = scrapy.Field()
    category = scrapy.Field()        # 政策 / 经济 / 社会 / 生态 etc.
    tags = scrapy.Field()            # list[str]


class EssayItem(scrapy.Item):
    """A model essay / opinion piece for 申论 reference."""

    source_url = scrapy.Field()
    source_name = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    topic = scrapy.Field()           # 乡村振兴 / 基层治理 / 经济发展 etc.
