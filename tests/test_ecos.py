import json
import unittest

from market_agent.collectors.base import CollectContext
from market_agent.collectors.ecos import (
    BaseRateCollector,
    EcosApiError,
    build_base_rate_evidence,
    find_base_rate,
    parse_key_statistic_response,
)


def key_stat_payload(rows: list[dict]) -> bytes:
    return json.dumps(
        {"KeyStatisticList": {"list_total_count": len(rows), "row_count": len(rows), "row": rows}}
    ).encode("utf-8")


BASE_RATE_ROW = {
    "CLASS_NAME": "시장금리",
    "KEYSTAT_NAME": "한국은행 기준금리",
    "DATA_VALUE": "2.5",
    "CYCLE": "20260601",
    "UNIT_NAME": "%",
}
OTHER_ROW = {
    "CLASS_NAME": "환율",
    "KEYSTAT_NAME": "원/달러 환율(종가)",
    "DATA_VALUE": "1400.0",
    "CYCLE": "20260601",
    "UNIT_NAME": "원",
}


class ParseKeyStatisticResponseTests(unittest.TestCase):
    def test_parses_rows_on_success(self) -> None:
        payload = key_stat_payload([BASE_RATE_ROW, OTHER_ROW])

        rows = parse_key_statistic_response(payload)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["KEYSTAT_NAME"], "한국은행 기준금리")

    def test_raises_on_error_result(self) -> None:
        payload = json.dumps(
            {"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}
        ).encode("utf-8")

        with self.assertRaises(EcosApiError):
            parse_key_statistic_response(payload)

    def test_raises_on_invalid_json(self) -> None:
        with self.assertRaises(EcosApiError):
            parse_key_statistic_response(b"not json")


class FindBaseRateTests(unittest.TestCase):
    def test_finds_base_rate_row(self) -> None:
        row = find_base_rate([OTHER_ROW, BASE_RATE_ROW])
        self.assertIsNotNone(row)
        self.assertEqual(row["DATA_VALUE"], "2.5")

    def test_returns_none_when_missing(self) -> None:
        self.assertIsNone(find_base_rate([OTHER_ROW]))


class BuildBaseRateEvidenceTests(unittest.TestCase):
    def test_builds_evidence_from_row(self) -> None:
        evidence = build_base_rate_evidence(BASE_RATE_ROW)

        self.assertEqual(len(evidence), 1)
        self.assertIn("2.5", evidence[0].title)
        self.assertEqual(evidence[0].impact, 0.0)
        self.assertEqual(evidence[0].category, "policy")
        self.assertIn("기준금리", evidence[0].tags)

    def test_returns_empty_when_row_missing(self) -> None:
        self.assertEqual(build_base_rate_evidence(None), [])


class FakeEcosClient:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.call_count = 0

    def fetch_key_statistics(self, count: int = 100) -> list[dict]:
        self.call_count += 1
        return self.rows


class BaseRateCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        BaseRateCollector._cache = {}

    def test_collect_returns_base_rate_evidence(self) -> None:
        client = FakeEcosClient([BASE_RATE_ROW, OTHER_ROW])
        collector = BaseRateCollector(client)
        context = CollectContext(address="아무 주소", radius_km=3)

        evidence = collector.collect(context)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(client.call_count, 1)

    def test_collect_caches_within_same_day(self) -> None:
        client = FakeEcosClient([BASE_RATE_ROW])
        collector = BaseRateCollector(client)
        context = CollectContext(address="아무 주소", radius_km=3)

        collector.collect(context)
        collector.collect(context)

        self.assertEqual(client.call_count, 1)


if __name__ == "__main__":
    unittest.main()
