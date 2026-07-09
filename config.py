import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
    NAVER_SEARCH_ADS_API_KEY = os.getenv("NAVER_SEARCH_ADS_API_KEY", "")
    NAVER_SEARCH_ADS_SECRET = os.getenv("NAVER_SEARCH_ADS_SECRET", "")
    NAVER_SEARCH_ADS_CUSTOMER_ID = os.getenv("NAVER_SEARCH_ADS_CUSTOMER_ID", "")
    NAVER_ID = os.getenv("NAVER_ID", "")
    NAVER_PW = os.getenv("NAVER_PW", "")

    TISTORY_ACCESS_TOKEN = os.getenv("TISTORY_ACCESS_TOKEN", "")
    TISTORY_BLOG_NAME = os.getenv("TISTORY_BLOG_NAME", "")

    INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

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
