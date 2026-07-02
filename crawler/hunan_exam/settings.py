"""Scrapy settings for Hunan Exam crawler."""

BOT_NAME = "hunan_exam_crawler"
SPIDER_MODULES = ["hunan_exam.spiders"]
NEWSPIDER_MODULE = "hunan_exam.spiders"

# Obey robots.txt
ROBOTSTXT_OBEY = True

# Polite download delay
DOWNLOAD_DELAY = 3  # seconds between requests to same domain
RANDOMIZE_DOWNLOAD_DELAY = True

# Identify ourselves
USER_AGENT = (
    "HunanExamAssistant/1.0 (+https://github.com/hunan-exam-assistant; "
    "educational research; contact: admin@example.com)"
)

# Pipelines
ITEM_PIPELINES = {
    "hunan_exam.pipelines.DuplicateFilterPipeline": 100,
    "hunan_exam.pipelines.PostgreSQLPipeline": 200,
}

# Respect caching
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400  # 1 day
HTTPCACHE_DIR = "httpcache"

# Auto-throttle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# Logging
LOG_LEVEL = "INFO"

# Backend API target for pipeline ingestion
BACKEND_API_BASE = "http://localhost:8000"
BACKEND_API_TOKEN = ""  # Set via environment or command line: -s BACKEND_API_TOKEN=...
