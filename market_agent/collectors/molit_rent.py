from __future__ import annotations

import statistics
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

from market_agent.collectors.base import CollectContext
from market_agent.collectors.data_go_kr import DataGoKrApiError, parse_xml_items
from market_agent.collectors.molit import (
    MIN_SAMPLE_SIZE,
    filter_relevant,
    price_per_area,
    recent_year_months,
)
from market_agent.models import EvidenceItem


RentApiError = DataGoKrApiError

# ⚠️ 검증 대기중 (2026-07-09 기준): 아래 base_url과 필드명은 국토교통부_아파트 전월세
# 실거래자료 API의 일반적으로 알려진 이름/스키마를 바탕으로 작성했습니다. 매매
# 실거래가 API 때도 문서상 이름(RTMSDataSvcAptTradeDev)과 실제 End Point
# (RTMSDataSvcAptTrade), 성공 코드(00 vs 000)가 달라서 실제로 버그가 났었습니다.
# data.go.kr 활용신청이 승인되면 승인 화면의 End Point/필드 스펙을 스크린샷으로
# 확인하고 아래 값을 먼저 재검증한 뒤 실제 키로 로컬 테스트할 것.
class RentClient:
    """Client for the MOLIT apartment 전월세(rent) open API via data.go.kr.

    Docs (as of writing, unverified against actual approval screen):
    https://www.data.go.kr/data/15126474/openapi.do
    (국토교통부_아파트 전월세 실거래가 자료)
    """

    base_url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

    def __init__(self, service_key: str, timeout: float = 10.0) -> None:
        self.service_key = service_key
        self.timeout = timeout

    def fetch_rents(
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
        url = f"{self.base_url}?serviceKey={self.service_key}&{params}"
        request = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RentApiError(f"MOLIT rent API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RentApiError(f"MOLIT rent API request failed: {exc}") from exc

        return parse_xml_items(payload)


def normalize_amount(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)  # 만원 단위
    except ValueError:
        return None


def is_jeonse(record: dict[str, Any]) -> bool:
    """True if this rent record is a pure 전세 (no monthly rent component).

    월세 계약(보증금 낮음 + 매달 월세)까지 전세가율 계산에 섞으면 왜곡되므로
    monthlyRent가 0/빈 값인 순수 전세 건만 사용한다.
    """
    monthly = normalize_amount(record.get("monthlyRent"))
    return not monthly


def deposit_per_area(record: dict[str, Any]) -> float | None:
    deposit = normalize_amount(record.get("deposit"))
    try:
        area = float(record.get("excluUseAr") or 0)
    except ValueError:
        area = 0.0
    if not deposit or not area:
        return None
    return deposit / area  # 만원 per m²


def build_jeonse_evidence(
    trade_records: list[dict[str, Any]], rent_records: list[dict[str, Any]]
) -> list[EvidenceItem]:
    trade_prices = [p for p in (price_per_area(r) for r in trade_records) if p]
    jeonse_records = [r for r in rent_records if is_jeonse(r)]
    jeonse_prices = [p for p in (deposit_per_area(r) for r in jeonse_records) if p]

    if not trade_prices or not jeonse_prices:
        return [
            EvidenceItem(
                title="전세가율 계산에 필요한 실거래 데이터 부족",
                summary="최근 매매 또는 순수 전세 실거래 표본이 없어 전세가율을 계산하지 못했습니다.",
                source="MOLIT",
                category="market_data",
                sentiment="neutral",
                reliability=0.3,
                impact=0.0,
                tags=["전세가율", "데이터부족"],
            )
        ]

    enough_samples = (
        len(trade_prices) >= MIN_SAMPLE_SIZE and len(jeonse_prices) >= MIN_SAMPLE_SIZE
    )
    if not enough_samples:
        return [
            EvidenceItem(
                title=f"전세가율 계산 표본 부족 (매매 {len(trade_prices)}건, 전세 {len(jeonse_prices)}건)",
                summary="매매 또는 전세 표본이 3건 미만이라 전세가율을 신뢰도 있게 계산하기 어렵습니다.",
                source="MOLIT",
                category="market_data",
                sentiment="neutral",
                reliability=0.4,
                impact=0.0,
                tags=["전세가율", "표본부족"],
            )
        ]

    trade_median = statistics.median(trade_prices)
    jeonse_median = statistics.median(jeonse_prices)
    ratio = (jeonse_median / trade_median) * 100

    # 일반적인 부동산 실무 기준(정확한 임계값은 지역/시기마다 다를 수 있음):
    # 전세가율이 높을수록(70%+) 매매가-전세가 갭이 작아 갭투자 부담이 낮고
    # 실수요가 탄탄하다는 신호. 반대로 50% 미만이면 갭이 커서 갭투자發
    # 변동성 리스크나 매매가 고평가 우려로 해석하는 경우가 많음.
    if ratio >= 70:
        sentiment = "positive"
    elif ratio < 50:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    impact = round(max(-4.0, min(4.0, (ratio - 60) * 0.08)), 2)

    return [
        EvidenceItem(
            title=f"전세가율 {ratio:.1f}% (전세 중위 {jeonse_median:,.0f}만원/㎡, 매매 중위 {trade_median:,.0f}만원/㎡)",
            summary=(
                "국토부 아파트 매매·전세 실거래 자료 기준 최근 3개월 중위가로 계산한 전세가율입니다 "
                f"(매매 표본 {len(trade_prices)}건, 전세 표본 {len(jeonse_prices)}건)."
            ),
            source="MOLIT",
            category="market_data",
            sentiment=sentiment,
            reliability=0.85,
            impact=impact,
            tags=["전세가율"],
        )
    ]


class JeonseRatioCollector:
    """Combines the existing 매매(trade) client and the new 전월세(rent)
    client to produce a 전세가율(jeonse ratio) evidence item."""

    def __init__(
        self,
        trade_client: Any,
        rent_client: RentClient,
        reference_date: date | None = None,
    ) -> None:
        self.trade_client = trade_client
        self.rent_client = rent_client
        self.reference_date = reference_date or date.today()

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        lawd_cd = context.sigungu_code
        if not lawd_cd:
            return []

        region_3depth = context.location.region_3depth if context.location else None
        apartment_name = context.apartment_name

        recent_months = recent_year_months(self.reference_date, 3, offset=0)

        trade_records = filter_relevant(
            self._fetch_months(self.trade_client.fetch_trades, lawd_cd, recent_months),
            region_3depth,
            apartment_name,
        )
        rent_records = filter_relevant(
            self._fetch_months(self.rent_client.fetch_rents, lawd_cd, recent_months),
            region_3depth,
            apartment_name,
        )

        return build_jeonse_evidence(trade_records, rent_records)

    def _fetch_months(self, fetch_fn, lawd_cd: str, months: list[str]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for year_month in months:
            try:
                records.extend(fetch_fn(lawd_cd, year_month))
            except RentApiError:
                continue
        return records
