from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    NAVER_SEARCH_ADS_API_KEY = os.getenv("NAVER_SEARCH_ADS_API_KEY", "")
    NAVER_SEARCH_ADS_SECRET = os.getenv("NAVER_SEARCH_ADS_SECRET", "")
    NAVER_SEARCH_ADS_CUSTOMER_ID = os.getenv("NAVER_SEARCH_ADS_CUSTOMER_ID", "")

    BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "")
    HEALTH_BLOGGER_BLOG_ID = os.getenv("HEALTH_BLOGGER_BLOG_ID", "9117411480882444840")
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

    DEFAULT_CATEGORY = os.getenv("DEFAULT_CATEGORY", "정보")
    POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "5"))
    KEYWORD_LIMIT = int(os.getenv("KEYWORD_LIMIT", "10"))

    CLAUDE_MODEL = "claude-opus-4-8"

    def validate(self, require: list[str] | None = None) -> list[str]:
        missing = []
        checks = require or ["ANTHROPIC_API_KEY"]
        for key in checks:
            if not getattr(self, key, ""):
                missing.append(key)
        return missing


config = Config()
