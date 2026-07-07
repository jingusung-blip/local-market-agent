from __future__ import annotations

import statistics
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

from market_agent.collectors.base import CollectContext
from market_agent.models import EvidenceItem


M2_PER_PYEONG = 3.3058
RECENT_WINDOW_MONTHS = 3
BASELINE_WINDOW_MONTHS = 3
MIN_SAMPLE_SIZE = 3


class MolitApiError(RuntimeError):
    pass


class MolitClient:
    """Client for the Ministry of Land, Infrastructure and Transport (MOLIT)
    apartment trade (실거래가) open API, served through data.go.kr.

    Docs: https://www.data.go.kr/data/15058747/openapi.do
    (국토교통부_아파트매매 실거래자료)

    Requires a service key issued from data.go.kr (`MOLIT_API_KEY`). Unlike
    news/geocoding APIs, there is no meaningful offline fallback for this
    data, so callers should skip this collector entirely when no key is
    configured rather than fabricate numbers.
    """

    base_url = (
        "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    )

    def __init__(self, service_key: str, timeout: float = 10.0) -> None:
        self.service_key = service_key
        self.timeout = timeout

    def fetch_trades(
        self, lawd_cd: str, deal_ymd: str, num_of_rows: int = 300
    ) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "LAWD_CD": lawd_cd,
                "DEAL_YMD": deal_ymd,
                "numOfRows": num_of_rows,
                "pageNo": 1,
            }
        )
        # data.go.kr service keys are issued already percent-encoded, so we
        # append it raw instead of running it through urlencode again
        # (double-encoding is a common cause of "SERVICE KEY IS NOT REGISTERED"
        # errors with this API family).
        url = f"{self.base_url}?serviceKey={self.service_key}&{params}"
        request = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MolitApiError(f"MOLIT API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise MolitApiError(f"MOLIT API request failed: {exc}") from exc

        return parse_trade_items(payload)


def parse_trade_items(payload: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise MolitApiError(f"MOLIT API returned an unparseable response: {exc}") from exc

    header = root.find("header")
    if header is not None:
        result_code = (header.findtext("resultCode") or "").strip()
        # This API family isn't consistent about success-code width: some
        # data.go.kr services use "00", this one returns "000". Treat any
        # all-zero code as success instead of hardcoding one length.
        if result_code and set(result_code) != {"0"}:
            raise MolitApiError(
                f"MOLIT API error {result_code}: {header.findtext('resultMsg')}"
            )

    items: list[dict[str, Any]] = []
    for item in root.findall("./body/items/item"):
        record = {child.tag: (child.text or "").strip() for child in item}
        items.append(record)
    return items


def normalize_amount(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)  # 만원 단위
    except ValueError:
        return None


def price_per_area(record: dict[str, Any]) -> float | None:
    amount = normalize_amount(record.get("dealAmount"))
    try:
        area = float(record.get("excluUseAr") or 0)
    except ValueError:
        area = 0.0
    if not amount or not area:
        return None
    return amount / area  # 만원 per m²


def _norm(text: str | None) -> str:
    return (text or "").replace(" ", "")


def filter_relevant(
    records: list[dict[str, Any]],
    region_3depth: str | None,
    apartment_name: str | None,
) -> list[dict[str, Any]]:
    """Narrow sigungu-wide trade records down to the target 동/단지 when we
    can, but fall back to the wider set instead of returning nothing if the
    narrower filter doesn't match (name spelling in MOLIT data can differ
    slightly from Kakao's)."""
    result = records
    dong = _norm(region_3depth)
    if dong:
        dong_matches = [r for r in result if dong in _norm(r.get("umdNm"))]
        if dong_matches:
            result = dong_matches

    apt = _norm(apartment_name)
    if apt:
        apt_matches = [
            r for r in result if apt in _norm(r.get("aptNm")) or _norm(r.get("aptNm")) in apt
        ]
        if apt_matches:
            result = apt_matches

    return result


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def recent_year_months(reference: date, count: int, offset: int = 0) -> list[str]:
    months = []
    for i in range(count):
        y, m = shift_month(reference.year, reference.month, -(offset + i))
        months.append(f"{y:04d}{m:02d}")
    return months


def build_market_evidence(
    recent: list[dict[str, Any]], baseline: list[dict[str, Any]]
) -> list[EvidenceItem]:
    recent_prices = [p for p in (price_per_area(r) for r in recent) if p]
    baseline_prices = [p for p in (price_per_area(r) for r in baseline) if p]

    if not recent_prices:
        return [
            EvidenceItem(
                title="반경 시군구 내 최근 실거래 데이터 없음",
                summary="최근 3개월 국토부 아파트매매 실거래 자료에서 조건에 맞는 거래를 찾지 못했습니다.",
                source="MOLIT",
                category="market_data",
                sentiment="neutral",
                reliability=0.3,
                impact=0.0,
                tags=["실거래가", "데이터부족"],
            )
        ]

    recent_median = statistics.median(recent_prices)
    recent_pyeong = recent_median * M2_PER_PYEONG
    enough_samples = len(recent_prices) >= MIN_SAMPLE_SIZE and len(baseline_prices) >= MIN_SAMPLE_SIZE

    if not enough_samples:
        return [
            EvidenceItem(
                title=f"최근 3개월 실거래 평균 {recent_pyeong:,.0f}만원/평 (표본 {len(recent_prices)}건)",
                summary="직전 3개월과 비교할 거래량이 부족해 추세 대신 최근 평균가만 반영했습니다.",
                source="MOLIT",
                category="market_data",
                sentiment="neutral",
                reliability=0.55,
                impact=0.0,
                tags=["실거래가", "표본부족"],
            )
        ]

    baseline_median = statistics.median(baseline_prices)
    pct_change = ((recent_median - baseline_median) / baseline_median) * 100
    if pct_change >= 1.5:
        sentiment = "positive"
    elif pct_change <= -1.5:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    impact = round(max(-6.0, min(6.0, pct_change * 0.5)), 2)

    return [
        EvidenceItem(
            title=f"최근 3개월 실거래 {recent_pyeong:,.0f}만원/평, 직전 3개월 대비 {pct_change:+.1f}%",
            summary=(
                "국토부 아파트매매 실거래 자료 기준 최근 3개월 평균가와 직전 3개월 평균가를 비교했습니다 "
                f"(최근 표본 {len(recent_prices)}건, 직전 표본 {len(baseline_prices)}건)."
            ),
            source="MOLIT",
            category="market_data",
            sentiment=sentiment,
            reliability=0.9,
            impact=impact,
            tags=["실거래가"],
        )
    ]


class MolitTransactionCollector:
    def __init__(self, client: MolitClient, reference_date: date | None = None) -> None:
        self.client = client
        self.reference_date = reference_date or date.today()

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        lawd_cd = context.sigungu_code
        if not lawd_cd:
            return []

        region_3depth = context.location.region_3depth if context.location else None
        apartment_name = context.apartment_name

        recent_months = recent_year_months(self.reference_date, RECENT_WINDOW_MONTHS, offset=0)
        baseline_months = recent_year_months(
            self.reference_date, BASELINE_WINDOW_MONTHS, offset=RECENT_WINDOW_MONTHS
        )

        recent_records = filter_relevant(
            self._fetch_months(lawd_cd, recent_months), region_3depth, apartment_name
        )
        baseline_records = filter_relevant(
            self._fetch_months(lawd_cd, baseline_months), region_3depth, apartment_name
        )

        return build_market_evidence(recent_records, baseline_records)

    def _fetch_months(self, lawd_cd: str, months: list[str]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for year_month in months:
            try:
                records.extend(self.client.fetch_trades(lawd_cd, year_month))
            except MolitApiError:
                continue
        return records
