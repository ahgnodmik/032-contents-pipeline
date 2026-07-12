from __future__ import annotations
import hashlib
import hmac
import time
import base64
from dataclasses import dataclass, field

import requests
from pytrends.request import TrendReq

from config import config


@dataclass
class Keyword:
    text: str
    monthly_search_pc: int = 0
    monthly_search_mobile: int = 0
    competition: float = 0.0
    score: float = 0.0

    @property
    def total_searches(self) -> int:
        return self.monthly_search_pc + self.monthly_search_mobile


@dataclass
class KeywordResult:
    seed: str
    keywords: list[Keyword] = field(default_factory=list)


class NaverSearchAdsResearcher:
    BASE_URL = "https://api.searchad.naver.com"

    def _sign(self, timestamp: str, method: str, path: str) -> str:
        message = f"{timestamp}.{method}.{path}"
        signature = hmac.new(
            config.NAVER_SEARCH_ADS_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _headers(self, method: str, path: str) -> dict:
        timestamp = str(int(time.time() * 1000))
        return {
            "X-Timestamp": timestamp,
            "X-API-KEY": config.NAVER_SEARCH_ADS_API_KEY,
            "X-Customer": config.NAVER_SEARCH_ADS_CUSTOMER_ID,
            "X-Signature": self._sign(timestamp, method, path),
        }

    def get_related_keywords(self, seed: str, limit: int = 20) -> list[Keyword]:
        path = "/keywordstool"
        params = {"hintKeywords": seed, "showDetail": "1"}
        resp = requests.get(
            self.BASE_URL + path,
            headers=self._headers("GET", path),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        def _to_int(val) -> int:
            # Naver API는 소량일 때 "< 10" 같은 문자열을 반환하기도 함
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        def _to_float(val) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return 0.0

        keywords = []
        for item in data.get("keywordList", [])[:limit]:
            pc = _to_int(item.get("monthlyPcQcCnt", 0))
            mobile = _to_int(item.get("monthlyMobileQcCnt", 0))
            competition = _to_float(item.get("compIdx", 0.0))
            total = pc + mobile
            score = total * (1 - competition) if total > 0 else 0
            keywords.append(
                Keyword(
                    text=item["relKeyword"],
                    monthly_search_pc=pc,
                    monthly_search_mobile=mobile,
                    competition=competition,
                    score=score,
                )
            )

        keywords.sort(key=lambda k: k.score, reverse=True)
        return keywords


class GoogleTrendsResearcher:
    def __init__(self):
        self.pytrends = TrendReq(hl="ko", tz=540)

    def get_related_keywords(self, seed: str, limit: int = 20) -> list[Keyword]:
        self.pytrends.build_payload([seed], cat=0, timeframe="today 3-m", geo="KR")
        related = self.pytrends.related_queries()

        keywords = []
        queries = related.get(seed, {})
        top = queries.get("top")
        if top is not None and not top.empty:
            for _, row in top.head(limit).iterrows():
                keywords.append(
                    Keyword(
                        text=row["query"],
                        score=float(row["value"]),
                    )
                )
        return keywords

    def get_trending_topics(self, limit: int = 10) -> list[str]:
        try:
            trending = self.pytrends.trending_searches(pn="south_korea")
            return trending[0].tolist()[:limit]
        except Exception:
            return []


def research_keywords(seed: str, limit: int | None = None) -> KeywordResult:
    limit = limit or config.KEYWORD_LIMIT
    result = KeywordResult(seed=seed)

    if config.NAVER_SEARCH_ADS_API_KEY and config.NAVER_SEARCH_ADS_SECRET:
        try:
            researcher = NaverSearchAdsResearcher()
            result.keywords = researcher.get_related_keywords(seed, limit)
            return result
        except Exception as e:
            print(f"[keyword] Naver Ads API 실패, Google Trends로 전환: {e}")

    try:
        researcher = GoogleTrendsResearcher()
        result.keywords = researcher.get_related_keywords(seed, limit)
    except Exception as e:
        print(f"[keyword] Google Trends 실패: {e}")

    if not result.keywords:
        print(f"[keyword] 리서치 결과 없음 — 시드 키워드 직접 사용: {seed}")
        result.keywords = [Keyword(text=seed, score=100.0)]

    return result
