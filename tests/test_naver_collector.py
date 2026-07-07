import unittest
from datetime import datetime, timezone
from email.utils import format_datetime

from market_agent.collectors.base import CollectContext
from market_agent.collectors.naver import (
    NaverNewsPolicyCollector,
    apply_region_relevance,
    build_search_target,
    is_recent_news_item,
    recency_multiplier,
)
from market_agent.models import EvidenceItem, GeoPoint


def pubdate(year: int, month: int, day: int) -> str:
    return format_datetime(datetime(year, month, day, tzinfo=timezone.utc), usegmt=True)


class FakeNaverClient:
    def __init__(self, items: list[dict[str, str]]) -> None:
        self.items = items

    def news(self, query: str, display: int = 5) -> list[dict[str, str]]:
        return self.items[:display]

    def web(self, query: str, display: int = 5) -> list[dict[str, str]]:
        return []


class NaverCollectorTests(unittest.TestCase):
    def test_recent_news_filter_excludes_old_articles(self) -> None:
        now = datetime(2026, 5, 13, tzinfo=timezone.utc)

        self.assertTrue(
            is_recent_news_item({"pubDate": pubdate(2025, 8, 1)}, max_age_days=730, now=now)
        )
        self.assertFalse(
            is_recent_news_item({"pubDate": pubdate(2020, 1, 1)}, max_age_days=730, now=now)
        )
        self.assertFalse(is_recent_news_item({}, max_age_days=730, now=now))

    def test_collector_keeps_recent_news_and_drops_old_news(self) -> None:
        recent = pubdate(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month, 1)
        old = pubdate(2020, 1, 1)
        collector = NaverNewsPolicyCollector(
            FakeNaverClient(
                [
                    {
                        "title": "오래된 개발 호재",
                        "description": "오래된 기사입니다.",
                        "originallink": "https://example.com/old",
                        "pubDate": old,
                    },
                    {
                        "title": "최신 교통 호재",
                        "description": "최근 교통 개선 기대가 있습니다.",
                        "originallink": "https://example.com/recent",
                        "pubDate": recent,
                    },
                ]
            ),
            per_query=5,
            max_news_age_days=730,
        )

        evidence = collector.collect(
            CollectContext(address="서울 테스트 아파트", radius_km=3, apartment_name=None)
        )

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].url, "https://example.com/recent")
        self.assertGreater(evidence[0].reliability, 0.72)

    def test_recency_multiplier_downweights_articles_after_one_year(self) -> None:
        now = datetime(2026, 5, 13, tzinfo=timezone.utc)

        fresh = recency_multiplier(datetime(2026, 5, 1, tzinfo=timezone.utc), now=now)
        older = recency_multiplier(datetime(2025, 1, 1, tzinfo=timezone.utc), now=now)

        self.assertGreater(fresh, older)

    def test_build_search_target_adds_region_hint_for_bare_apartment_name(self) -> None:
        location = GeoPoint(
            address="서울 강남구 대치동 123",
            latitude=37.5,
            longitude=127.0,
            region_1depth="서울특별시",
            region_2depth="강남구",
            region_3depth="대치동",
        )
        context = CollectContext(
            address="",
            radius_km=3,
            apartment_name="래미안",
            location=location,
        )

        target = build_search_target(context)

        self.assertIn("강남구", target)
        self.assertIn("래미안", target)

    def test_build_search_target_unchanged_without_location(self) -> None:
        context = CollectContext(address="서울 테스트 아파트", radius_km=3, apartment_name=None)

        self.assertEqual(build_search_target(context), context.target_text)

    def test_apply_region_relevance_discounts_unrelated_hit(self) -> None:
        item = EvidenceItem(
            title="래미안 부산 사업 소식",
            summary="부산광역시에 있는 동명 단지 이야기입니다.",
            source="Naver News",
            category="news",
            sentiment="positive",
            reliability=0.8,
            impact=3.0,
        )

        apply_region_relevance(item, "강남구 래미안", ["서울특별시", "강남구", "대치동"])

        self.assertLess(item.reliability, 0.8)
        self.assertIn("지역확인필요", item.tags)

    def test_apply_region_relevance_keeps_matching_hit(self) -> None:
        item = EvidenceItem(
            title="강남구 래미안 인근 개발 호재",
            summary="강남구 대치동 일대 교통망 확충 소식입니다.",
            source="Naver News",
            category="news",
            sentiment="positive",
            reliability=0.8,
            impact=3.0,
        )

        apply_region_relevance(item, "강남구 래미안", ["서울특별시", "강남구", "대치동"])

        self.assertEqual(item.reliability, 0.8)
        self.assertNotIn("지역확인필요", item.tags)


if __name__ == "__main__":
    unittest.main()
