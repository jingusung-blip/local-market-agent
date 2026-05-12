from __future__ import annotations

import html
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from market_agent.collectors.base import CollectContext
from market_agent.keywords import classify_sentiment, estimate_impact, normalize_text
from market_agent.models import EvidenceItem


TAG_RE = re.compile(r"<[^>]+>")


GOOD_QUERIES = [
    "{target} 개발 호재",
    "{target} 교통 지하철 GTX",
    "{target} 재건축 재개발 정비사업",
    "{target} 상권 업무지구 일자리",
]

BAD_QUERIES = [
    "{target} 침수 화재 사고",
    "{target} 소음 악취 민원",
    "{target} 미분양 공급과잉 하락",
    "{target} 개발 지연 취소 무산",
]

POLICY_QUERIES = [
    "{target} 도시계획 지구단위계획",
    "{target} 지자체 정책 공고 고시",
    "{target} 정부 부동산 정책 규제",
    "{target} 공공주택 정비구역",
]


class NaverSearchError(RuntimeError):
    pass


class NaverSearchClient:
    base_url = "https://openapi.naver.com/v1/search"

    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout

    def _search(self, endpoint: str, query: str, display: int = 5) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "query": query,
                "display": max(1, min(display, 20)),
                "start": 1,
                "sort": "date",
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}/{endpoint}.json?{params}",
            headers={
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise NaverSearchError(f"Naver API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise NaverSearchError(f"Naver API request failed: {exc}") from exc

        import json

        return list(json.loads(payload).get("items", []))

    def news(self, query: str, display: int = 5) -> list[dict[str, Any]]:
        return self._search("news", query, display=display)

    def web(self, query: str, display: int = 5) -> list[dict[str, Any]]:
        return self._search("webkr", query, display=display)


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    without_tags = TAG_RE.sub("", value)
    return normalize_text(html.unescape(without_tags))


class NaverNewsPolicyCollector:
    def __init__(self, client: NaverSearchClient, per_query: int = 5) -> None:
        self.client = client
        self.per_query = per_query

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        seen: set[str] = set()

        for query_template in GOOD_QUERIES:
            evidence.extend(
                self._collect_news_query(
                    query_template.format(target=context.target_text),
                    "positive",
                    seen,
                )
            )

        for query_template in BAD_QUERIES:
            evidence.extend(
                self._collect_news_query(
                    query_template.format(target=context.target_text),
                    "negative",
                    seen,
                )
            )

        for query_template in POLICY_QUERIES:
            evidence.extend(
                self._collect_policy_query(
                    query_template.format(target=context.target_text),
                    seen,
                )
            )

        return evidence

    def _collect_news_query(
        self, query: str, default_sentiment: str, seen: set[str]
    ) -> list[EvidenceItem]:
        items = self.client.news(query, display=self.per_query)
        return [
            self._to_evidence(item, "news", "Naver News", default_sentiment, seen)
            for item in items
            if self._dedupe_key(item) not in seen
        ]

    def _collect_policy_query(self, query: str, seen: set[str]) -> list[EvidenceItem]:
        results: list[EvidenceItem] = []
        for item in self.client.web(query, display=self.per_query):
            key = self._dedupe_key(item)
            if key in seen:
                continue
            results.append(self._to_evidence(item, "policy", "Naver Web", "neutral", seen))
        return results

    def _to_evidence(
        self,
        item: dict[str, Any],
        category: str,
        source: str,
        default_sentiment: str,
        seen: set[str],
    ) -> EvidenceItem:
        seen.add(self._dedupe_key(item))
        title = clean_html(item.get("title"))
        summary = clean_html(item.get("description"))
        text = f"{title} {summary}"
        sentiment, tags = classify_sentiment(text, default_sentiment)
        link = item.get("originallink") or item.get("link")
        return EvidenceItem(
            title=title or "(제목 없음)",
            summary=summary,
            source=source,
            category=category,
            sentiment=sentiment,
            url=link,
            published_at=item.get("pubDate"),
            reliability=0.72 if category == "news" else 0.68,
            impact=estimate_impact(text, category, default_sentiment),
            tags=tags,
        )

    @staticmethod
    def _dedupe_key(item: dict[str, Any]) -> str:
        return str(item.get("originallink") or item.get("link") or item.get("title"))
