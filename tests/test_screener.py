import unittest
from datetime import date

from market_agent.screener import (
    DistrictMomentum,
    compute_district_momentum,
    screen_districts,
)


def trade(deal_amount: str, area: str = "84") -> dict:
    return {"aptNm": "테스트", "umdNm": "테스트동", "dealAmount": deal_amount, "excluUseAr": area}


def rent(deposit: str, monthly_rent: str = "0", area: str = "84") -> dict:
    return {
        "aptNm": "테스트",
        "umdNm": "테스트동",
        "deposit": deposit,
        "monthlyRent": monthly_rent,
        "excluUseAr": area,
    }


class FakeTradeClient:
    def __init__(self, records_by_month: dict[str, list[dict]]) -> None:
        self.records_by_month = records_by_month
        self.calls: list[tuple[str, str]] = []

    def fetch_trades(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300) -> list[dict]:
        self.calls.append((lawd_cd, deal_ymd))
        return self.records_by_month.get(deal_ymd, [])


class FakeRentClient:
    def __init__(self, records_by_month: dict[str, list[dict]]) -> None:
        self.records_by_month = records_by_month

    def fetch_rents(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300) -> list[dict]:
        return self.records_by_month.get(deal_ymd, [])


# reference_date=2026-05-01 기준 recent_year_months()의 실제 산출값.
# recent(offset=0, count=3) = 최근 3개월, baseline(offset=3, count=3) = 그 이전 3개월.
RECENT_MONTHS = ["202605", "202604", "202603"]
BASELINE_MONTHS = ["202602", "202601", "202512"]


class ComputeDistrictMomentumTests(unittest.TestCase):
    def test_insufficient_sample_returns_no_pct_change(self) -> None:
        trade_client = FakeTradeClient({"202605": [trade("150,000")]})
        rent_client = FakeRentClient({})

        result = compute_district_momentum(
            trade_client, rent_client, "11680", "강남구", reference_date=date(2026, 5, 1)
        )

        self.assertFalse(result.sufficient_sample)
        self.assertIsNone(result.pct_change)
        self.assertIsNone(result.jeonse_ratio)

    def test_sufficient_sample_computes_pct_change_and_jeonse_ratio(self) -> None:
        trade_records: dict[str, list[dict]] = {}
        for m in RECENT_MONTHS:
            trade_records[m] = [trade(f"{150000 + i * 100}") for i in range(2)]
        for m in BASELINE_MONTHS:
            trade_records[m] = [trade(f"{130000 + i * 100}") for i in range(2)]

        rent_records = {m: [rent(f"{120000 + i * 100}") for i in range(4)] for m in RECENT_MONTHS}

        trade_client = FakeTradeClient(trade_records)
        rent_client = FakeRentClient(rent_records)

        result = compute_district_momentum(
            trade_client, rent_client, "11680", "강남구", reference_date=date(2026, 5, 1)
        )

        self.assertTrue(result.sufficient_sample)
        self.assertIsNotNone(result.pct_change)
        self.assertGreater(result.pct_change, 0)
        self.assertIsNotNone(result.jeonse_ratio)
        self.assertTrue(result.regulated)  # 서울 25개구는 전부 지정 상태 (2026-07-09 기준)

    def test_district_with_no_rent_client_skips_jeonse_ratio(self) -> None:
        trade_records: dict[str, list[dict]] = {}
        for m in RECENT_MONTHS:
            trade_records[m] = [trade(f"{150000 + i * 100}") for i in range(2)]
        for m in BASELINE_MONTHS:
            trade_records[m] = [trade(f"{130000 + i * 100}") for i in range(2)]
        trade_client = FakeTradeClient(trade_records)

        result = compute_district_momentum(
            trade_client, None, "11680", "강남구", reference_date=date(2026, 5, 1)
        )

        self.assertTrue(result.sufficient_sample)
        self.assertIsNone(result.jeonse_ratio)


class ScreenDistrictsTests(unittest.TestCase):
    def test_sorts_by_pct_change_descending_with_insufficient_sample_last(self) -> None:
        # 강남구: strong upward momentum (recent 200000대 vs baseline 150000대)
        # 종로구: mild/negative momentum (recent 95000대 vs baseline 100000대)
        # 중구: insufficient sample (데이터 없음)
        gangnam_records: dict[str, list[dict]] = {}
        for m in RECENT_MONTHS:
            gangnam_records[m] = [trade(f"{200000 + i * 100}") for i in range(6)]
        for m in BASELINE_MONTHS:
            gangnam_records[m] = [trade(f"{150000 + i * 100}") for i in range(6)]

        jongno_records: dict[str, list[dict]] = {}
        for m in RECENT_MONTHS:
            jongno_records[m] = [trade(f"{95000 + i * 100}") for i in range(6)]
        for m in BASELINE_MONTHS:
            jongno_records[m] = [trade(f"{100000 + i * 100}") for i in range(6)]

        class MultiDistrictTradeClient:
            def fetch_trades(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300):
                if lawd_cd == "11680":  # 강남구: big jump
                    return gangnam_records.get(deal_ymd, [])
                if lawd_cd == "11110":  # 종로구: flat/negative
                    return jongno_records.get(deal_ymd, [])
                return []  # 중구: no data at all

        districts = [("11680", "강남구"), ("11110", "종로구"), ("11140", "중구")]
        results = screen_districts(
            MultiDistrictTradeClient(), None, districts=districts, reference_date=date(2026, 5, 1)
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].name, "강남구")
        self.assertEqual(results[1].name, "종로구")
        self.assertEqual(results[2].name, "중구")
        self.assertFalse(results[2].sufficient_sample)

    def test_uses_default_seoul_districts_when_none_given(self) -> None:
        class EmptyTradeClient:
            def fetch_trades(self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300):
                return []

        results = screen_districts(EmptyTradeClient(), None, reference_date=date(2026, 5, 1))

        self.assertEqual(len(results), 25)
        self.assertTrue(all(isinstance(r, DistrictMomentum) for r in results))
        self.assertTrue(all(not r.sufficient_sample for r in results))


if __name__ == "__main__":
    unittest.main()
