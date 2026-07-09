import unittest

from market_agent.collectors.base import CollectContext
from market_agent.collectors.regulation import RegulationAreaCollector
from market_agent.models import GeoPoint
from market_agent.regulation_areas import is_regulated_area


class IsRegulatedAreaTests(unittest.TestCase):
    def test_all_seoul_districts_are_regulated(self) -> None:
        self.assertTrue(is_regulated_area("서울특별시", "강남구"))
        self.assertTrue(is_regulated_area("서울특별시", "노원구"))
        self.assertTrue(is_regulated_area("서울특별시", "은평구"))

    def test_listed_gyeonggi_area_is_regulated(self) -> None:
        self.assertTrue(is_regulated_area("경기도", "성남시 분당구"))
        self.assertTrue(is_regulated_area("경기도", "과천시"))
        self.assertTrue(is_regulated_area("경기도", "구리시"))

    def test_unlisted_gyeonggi_area_is_not_regulated(self) -> None:
        self.assertFalse(is_regulated_area("경기도", "파주시"))
        self.assertFalse(is_regulated_area("경기도", "고양시 일산동구"))

    def test_other_region_is_not_regulated(self) -> None:
        self.assertFalse(is_regulated_area("부산광역시", "해운대구"))

    def test_missing_region_returns_false(self) -> None:
        self.assertFalse(is_regulated_area(None, None))


class RegulationAreaCollectorTests(unittest.TestCase):
    def test_collect_returns_empty_without_location(self) -> None:
        collector = RegulationAreaCollector()
        context = CollectContext(address="주소 없음", radius_km=3, location=None)

        self.assertEqual(collector.collect(context), [])

    def test_collect_flags_regulated_seoul_district(self) -> None:
        collector = RegulationAreaCollector()
        location = GeoPoint(
            address="서울 강남구 대치동",
            latitude=37.5,
            longitude=127.05,
            region_1depth="서울특별시",
            region_2depth="강남구",
        )
        context = CollectContext(address="서울 강남구 대치동", radius_km=3, location=location)

        evidence = collector.collect(context)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].sentiment, "negative")
        self.assertEqual(evidence[0].category, "policy")
        self.assertIn("규제지역", evidence[0].tags)
        self.assertLess(evidence[0].impact, 0)

    def test_collect_reports_unregulated_area_neutrally(self) -> None:
        collector = RegulationAreaCollector()
        location = GeoPoint(
            address="경기 파주시 금촌동",
            latitude=37.8,
            longitude=126.7,
            region_1depth="경기도",
            region_2depth="파주시",
        )
        context = CollectContext(address="경기 파주시 금촌동", radius_km=3, location=location)

        evidence = collector.collect(context)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].sentiment, "neutral")
        self.assertEqual(evidence[0].impact, 0.0)


if __name__ == "__main__":
    unittest.main()
