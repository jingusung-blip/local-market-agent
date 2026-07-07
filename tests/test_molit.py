import unittest
from datetime import date

from market_agent.collectors.base import CollectContext
from market_agent.collectors.molit import (
    MolitApiError,
    MolitTransactionCollector,
    build_market_evidence,
    filter_relevant,
    parse_trade_items,
    price_per_area,
    recent_year_months,
)
from market_agent.models import GeoPoint


def trade(apt_nm: str, umd_nm: str, deal_amount: str, area: str) -> dict:
    return {"aptNm": apt_nm, "umdNm": umd_nm, "dealAmount": deal_amount, "excluUseAr": area}


class MolitParsingTests(unittest.TestCase):
    def test_parse_trade_items_reads_records(self) -> None:
        payload = """<?xml version="1.0" encoding="UTF-8"?>
        <response>
          <header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>
          <body>
            <items>
              <item>
                <aptNm>테스트아파트</aptNm>
                <umdNm>대치동</umdNm>
                <dealAmount>150,000</dealAmount>
                <excluUseAr>84.99</excluUseAr>
              </item>
            </items>
          </body>
        </response>""".encode("utf-8")

        items = parse_trade_items(payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["aptNm"], "테스트아파트")
        self.assertEqual(items[0]["dealAmount"], "150,000")

    def test_parse_trade_items_accepts_triple_zero_result_code(self) -> None:
        # This MOLIT/data.go.kr service returns resultCode "000" for success
        # (not "00" like most other data.go.kr APIs) -- regression test for
        # a real bug where this was misread as an error.
        payload = """<?xml version="1.0" encoding="UTF-8"?>
        <response>
          <header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
          <body>
            <items>
              <item>
                <aptNm>테스트아파트</aptNm>
                <umdNm>대치동</umdNm>
                <dealAmount>150,000</dealAmount>
                <excluUseAr>84.99</excluUseAr>
              </item>
            </items>
          </body>
        </response>""".encode("utf-8")

        items = parse_trade_items(payload)

        self.assertEqual(len(items), 1)

    def test_parse_trade_items_raises_on_real_error_code(self) -> None:
        payload = """<?xml version="1.0" encoding="UTF-8"?>
        <response>
          <header><resultCode>30</resultCode><resultMsg>SERVICE KEY IS NOT REGISTERED ERROR.</resultMsg></header>
          <body></body>
        </response>""".encode("utf-8")

        with self.assertRaises(MolitApiError):
            parse_trade_items(payload)

    def test_price_per_area_computes_per_m2_price(self) -> None:
        record = trade("테스트아파트", "대치동", "150,000", "100")
        self.assertAlmostEqual(price_per_area(record), 1500.0)

    def test_price_per_area_handles_missing_fields(self) -> None:
        self.assertIsNone(price_per_area({"aptNm": "x"}))


class MolitFilterTests(unittest.TestCase):
    def test_filter_relevant_narrows_by_dong_and_apartment(self) -> None:
        records = [
            trade("래미안", "대치동", "150,000", "84"),
            trade("래미안", "역삼동", "140,000", "84"),
            trade("자이", "대치동", "160,000", "84"),
        ]

        result = filter_relevant(records, region_3depth="대치동", apartment_name="래미안")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["umdNm"], "대치동")
        self.assertEqual(result[0]["aptNm"], "래미안")

    def test_filter_relevant_falls_back_when_no_exact_match(self) -> None:
        records = [trade("래미안", "대치동", "150,000", "84")]

        # apartment name spelled differently from MOLIT data -> falls back to
        # dong-level results instead of returning nothing.
        result = filter_relevant(records, region_3depth="대치동", apartment_name="래미안아파트단지")

        self.assertEqual(len(result), 1)


class MolitEvidenceTests(unittest.TestCase):
    def test_build_market_evidence_reports_no_data(self) -> None:
        evidence = build_market_evidence([], [])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].sentiment, "neutral")
        self.assertIn("데이터부족", evidence[0].tags)

    def test_build_market_evidence_flags_insufficient_sample(self) -> None:
        recent = [trade("A", "대치동", "150,000", "84")]
        evidence = build_market_evidence(recent, [])
        self.assertIn("표본부족", evidence[0].tags)
        self.assertEqual(evidence[0].impact, 0.0)

    def test_build_market_evidence_detects_price_increase(self) -> None:
        recent = [trade("A", "대치동", f"{150000 + i * 100}", "84") for i in range(4)]
        baseline = [trade("A", "대치동", f"{130000 + i * 100}", "84") for i in range(4)]

        evidence = build_market_evidence(recent, baseline)

        self.assertEqual(evidence[0].sentiment, "positive")
        self.assertGreater(evidence[0].impact, 0)

    def test_build_market_evidence_detects_price_decrease(self) -> None:
        recent = [trade("A", "대치동", f"{100000 + i * 100}", "84") for i in range(4)]
        baseline = [trade("A", "대치동", f"{130000 + i * 100}", "84") for i in range(4)]

        evidence = build_market_evidence(recent, baseline)

        self.assertEqual(evidence[0].sentiment, "negative")
        self.assertLess(evidence[0].impact, 0)


class RecentYearMonthsTests(unittest.TestCase):
    def test_recent_year_months_handles_year_rollover(self) -> None:
        months = recent_year_months(date(2026, 2, 1), count=3, offset=0)
        self.assertEqual(months, ["202602", "202601", "202512"])

    def test_recent_year_months_with_offset(self) -> None:
        months = recent_year_months(date(2026, 2, 1), count=2, offset=3)
        self.assertEqual(months, ["202511", "202510"])


class FakeMolitClient:
    def __init__(self, records_by_month: dict[str, list[dict]]) -> None:
        self.records_by_month = records_by_month

    def fetch_trades(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300) -> list[dict]:
        return self.records_by_month.get(deal_ymd, [])


class MolitTransactionCollectorTests(unittest.TestCase):
    def test_collect_returns_empty_without_sigungu_code(self) -> None:
        collector = MolitTransactionCollector(FakeMolitClient({}))
        context = CollectContext(address="주소 없음", radius_km=3, location=None)

        self.assertEqual(collector.collect(context), [])

    def test_collect_builds_evidence_when_sigungu_code_present(self) -> None:
        reference = date(2026, 5, 1)
        records_by_month = {
            "202605": [trade("래미안", "대치동", "150,000", "84")],
            "202604": [trade("래미안", "대치동", "149,000", "84")],
            "202603": [trade("래미안", "대치동", "148,000", "84")],
            "202602": [trade("래미안", "대치동", "130,000", "84")],
            "202601": [trade("래미안", "대치동", "129,000", "84")],
            "202512": [trade("래미안", "대치동", "128,000", "84")],
        }
        client = FakeMolitClient(records_by_month)
        collector = MolitTransactionCollector(client, reference_date=reference)
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
        self.assertEqual(evidence[0].sentiment, "positive")


if __name__ == "__main__":
    unittest.main()
