import unittest
from datetime import date

from market_agent.collectors.base import CollectContext
from market_agent.collectors.molit_rent import (
    JeonseRatioCollector,
    RentApiError,
    build_jeonse_evidence,
    deposit_per_area,
    is_jeonse,
)
from market_agent.models import GeoPoint


def trade(apt_nm: str, umd_nm: str, deal_amount: str, area: str) -> dict:
    return {"aptNm": apt_nm, "umdNm": umd_nm, "dealAmount": deal_amount, "excluUseAr": area}


def rent(apt_nm: str, umd_nm: str, deposit: str, monthly_rent: str, area: str) -> dict:
    return {
        "aptNm": apt_nm,
        "umdNm": umd_nm,
        "deposit": deposit,
        "monthlyRent": monthly_rent,
        "excluUseAr": area,
    }


class JeonseHelperTests(unittest.TestCase):
    def test_is_jeonse_true_when_no_monthly_rent(self) -> None:
        self.assertTrue(is_jeonse(rent("래미안", "대치동", "100,000", "0", "84")))
        self.assertTrue(is_jeonse(rent("래미안", "대치동", "100,000", "", "84")))

    def test_is_jeonse_false_when_monthly_rent_present(self) -> None:
        self.assertFalse(is_jeonse(rent("래미안", "대치동", "10,000", "50", "84")))

    def test_deposit_per_area_computes_per_m2_deposit(self) -> None:
        record = rent("래미안", "대치동", "100,000", "0", "100")
        self.assertAlmostEqual(deposit_per_area(record), 1000.0)

    def test_deposit_per_area_handles_missing_fields(self) -> None:
        self.assertIsNone(deposit_per_area({"aptNm": "x"}))


class BuildJeonseEvidenceTests(unittest.TestCase):
    def test_reports_no_data_when_either_side_missing(self) -> None:
        evidence = build_jeonse_evidence([], [])
        self.assertEqual(len(evidence), 1)
        self.assertIn("데이터부족", evidence[0].tags)
        self.assertEqual(evidence[0].sentiment, "neutral")

    def test_reports_insufficient_sample(self) -> None:
        trades = [trade("A", "대치동", "150,000", "84")]
        rents = [rent("A", "대치동", "100,000", "0", "84")]
        evidence = build_jeonse_evidence(trades, rents)
        self.assertIn("표본부족", evidence[0].tags)
        self.assertEqual(evidence[0].impact, 0.0)

    def test_high_jeonse_ratio_is_positive(self) -> None:
        trades = [trade("A", "대치동", f"{150000 + i * 10}", "84") for i in range(4)]
        # deposit/area ~= dealAmount/area * 0.85 -> ratio ~85%
        rents = [rent("A", "대치동", f"{127000 + i * 10}", "0", "84") for i in range(4)]

        evidence = build_jeonse_evidence(trades, rents)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].sentiment, "positive")
        self.assertGreater(evidence[0].impact, 0)
        self.assertIn("전세가율", evidence[0].tags)

    def test_low_jeonse_ratio_is_negative(self) -> None:
        trades = [trade("A", "대치동", f"{150000 + i * 10}", "84") for i in range(4)]
        # ratio ~= 40%
        rents = [rent("A", "대치동", f"{60000 + i * 10}", "0", "84") for i in range(4)]

        evidence = build_jeonse_evidence(trades, rents)

        self.assertEqual(evidence[0].sentiment, "negative")
        self.assertLess(evidence[0].impact, 0)

    def test_monthly_rent_records_are_excluded_from_ratio(self) -> None:
        trades = [trade("A", "대치동", f"{150000 + i * 10}", "84") for i in range(4)]
        # These look like high-deposit jeonse but have a monthly rent
        # component, so should NOT be counted as jeonse comparables.
        wolse = [rent("A", "대치동", f"{140000 + i * 10}", "50", "84") for i in range(4)]

        evidence = build_jeonse_evidence(trades, wolse)

        self.assertIn("데이터부족", evidence[0].tags)


class FakeTradeClient:
    def __init__(self, records_by_month: dict[str, list[dict]]) -> None:
        self.records_by_month = records_by_month

    def fetch_trades(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300) -> list[dict]:
        return self.records_by_month.get(deal_ymd, [])


class FakeRentClient:
    def __init__(self, records_by_month: dict[str, list[dict]]) -> None:
        self.records_by_month = records_by_month

    def fetch_rents(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300) -> list[dict]:
        return self.records_by_month.get(deal_ymd, [])


class JeonseRatioCollectorTests(unittest.TestCase):
    def test_collect_returns_empty_without_sigungu_code(self) -> None:
        collector = JeonseRatioCollector(FakeTradeClient({}), FakeRentClient({}))
        context = CollectContext(address="주소 없음", radius_km=3, location=None)

        self.assertEqual(collector.collect(context), [])

    def test_collect_builds_jeonse_evidence_when_sigungu_code_present(self) -> None:
        reference = date(2026, 5, 1)
        trade_records = {
            "202605": [trade("래미안", "대치동", "150,000", "84")],
            "202604": [trade("래미안", "대치동", "149,000", "84")],
            "202603": [trade("래미안", "대치동", "148,000", "84")],
        }
        rent_records = {
            "202605": [rent("래미안", "대치동", "127,000", "0", "84")],
            "202604": [rent("래미안", "대치동", "126,000", "0", "84")],
            "202603": [rent("래미안", "대치동", "125,000", "0", "84")],
        }
        collector = JeonseRatioCollector(
            FakeTradeClient(trade_records), FakeRentClient(rent_records), reference_date=reference
        )
        location = GeoPoint(
            address="서울 강남구 대치동",
            latitude=37.5,
            longitude=127.0,
            region_3depth="대치동",
            b_code="1168010100",
        )
        context = CollectContext(
            address="서울 강남구 대치동",
            radius_km=3,
            apartment_name="래미안",
            location=location,
        )

        evidence = collector.collect(context)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].category, "market_data")
        self.assertIn("전세가율", evidence[0].tags)

    def test_collect_ignores_rent_api_errors_for_individual_months(self) -> None:
        class FlakyRentClient:
            def fetch_rents(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300):
                raise RentApiError("service not registered")

        trade_records = {
            "202605": [trade("래미안", "대치동", "150,000", "84")],
            "202604": [trade("래미안", "대치동", "149,000", "84")],
            "202603": [trade("래미안", "대치동", "148,000", "84")],
        }
        collector = JeonseRatioCollector(
            FakeTradeClient(trade_records), FlakyRentClient(), reference_date=date(2026, 5, 1)
        )
        location = GeoPoint(
            address="서울 강남구 대치동",
            latitude=37.5,
            longitude=127.0,
            region_3depth="대치동",
            b_code="1168010100",
        )
        context = CollectContext(
            address="서울 강남구 대치동", radius_km=3, apartment_name="래미안", location=location
        )

        evidence = collector.collect(context)

        # No rent data (all months errored) -> falls back to the
        # "데이터부족" evidence item rather than raising.
        self.assertEqual(len(evidence), 1)
        self.assertIn("데이터부족", evidence[0].tags)


if __name__ == "__main__":
    unittest.main()
