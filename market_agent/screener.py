"""구/동 단위 상승동력 스크리닝.

기존 에이전트는 "주소/단지명 1개를 입력하면 그 주변만 분석"하는 조회형
구조다. 이 모듈은 그 반대 방향 — "여러 지역을 한 번에 훑어서 최근 가격
모멘텀이 강한 곳을 찾아주는" 스크리닝 기능을 추가한다. 기존 조회 기능은
그대로 두고, 같은 MOLIT 실거래가/전세가 클라이언트를 재사용해 지역
단위(시군구, LAWD_CD)로 반복 조회하는 방식이다.

⚠️ 지금은 서울 25개 자치구만 대상으로 한다. 아파트 단지 단위 스크리닝은
전국 단지 마스터 데이터가 별도로 필요해 범위 밖이다 (ROADMAP 참고).
"""
from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from market_agent.collectors.molit import price_per_area, recent_year_months
from market_agent.collectors.molit_rent import deposit_per_area, is_jeonse
from market_agent.regulation_areas import is_regulated_area


RECENT_WINDOW_MONTHS = 3
BASELINE_WINDOW_MONTHS = 3
MIN_TRADE_SAMPLE = 5
MIN_JEONSE_SAMPLE = 3

# 구 하나당 최대 6~9번(최근 3개월 + 직전 3개월 + 전세 3개월)의 실제 data.go.kr
# HTTP 호출이 필요하다. 25개 구를 순차로 돌리면 최악의 경우 150~225번의
# 네트워크 왕복이 직렬로 쌓여 Render 배포 환경에서 응답이 몇 분씩 걸리거나
# 아예 타임아웃나는 문제가 있었다 (2026-07-10, 실사용 중 "계속 로딩만 됨"
# 버그로 발견). 구 단위는 서로 완전히 독립적인 조회라 스레드로 병렬 처리해
# 전체 소요 시간을 25배가 아니라 대략 "가장 느린 구 1개" 수준으로 줄인다.
MAX_PARALLEL_DISTRICTS = 8

# 서울 25개 자치구 법정동코드(첫 5자리, LAWD_CD). 행정표준코드관리시스템
# (code.go.kr)의 법정동코드 기준이며, 행정동코드와는 다르므로 혼동 주의.
# 이 코드는 정부가 부여하는 고정 행정 코드라 국토부 API 이름/필드명과 달리
# 바뀔 가능성이 거의 없다.
SEOUL_DISTRICTS: list[tuple[str, str]] = [
    ("11110", "종로구"),
    ("11140", "중구"),
    ("11170", "용산구"),
    ("11200", "성동구"),
    ("11215", "광진구"),
    ("11230", "동대문구"),
    ("11260", "중랑구"),
    ("11290", "성북구"),
    ("11305", "강북구"),
    ("11320", "도봉구"),
    ("11350", "노원구"),
    ("11380", "은평구"),
    ("11410", "서대문구"),
    ("11440", "마포구"),
    ("11470", "양천구"),
    ("11500", "강서구"),
    ("11530", "구로구"),
    ("11545", "금천구"),
    ("11560", "영등포구"),
    ("11590", "동작구"),
    ("11620", "관악구"),
    ("11650", "서초구"),
    ("11680", "강남구"),
    ("11710", "송파구"),
    ("11740", "강동구"),
]


@dataclass
class DistrictMomentum:
    code: str
    name: str
    recent_sample: int
    baseline_sample: int
    sufficient_sample: bool
    pct_change: float | None = None
    jeonse_ratio: float | None = None
    regulated: bool = False


def _fetch_months(fetch_fn: Any, lawd_cd: str, months: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for year_month in months:
        try:
            records.extend(fetch_fn(lawd_cd, year_month))
        except Exception:
            continue
    return records


def compute_district_momentum(
    trade_client: Any,
    rent_client: Any,
    code: str,
    name: str,
    reference_date: date | None = None,
) -> DistrictMomentum:
    reference_date = reference_date or date.today()
    recent_months = recent_year_months(reference_date, RECENT_WINDOW_MONTHS, offset=0)
    baseline_months = recent_year_months(
        reference_date, BASELINE_WINDOW_MONTHS, offset=RECENT_WINDOW_MONTHS
    )

    recent_trades = _fetch_months(trade_client.fetch_trades, code, recent_months)
    baseline_trades = _fetch_months(trade_client.fetch_trades, code, baseline_months)

    recent_prices = [p for p in (price_per_area(r) for r in recent_trades) if p]
    baseline_prices = [p for p in (price_per_area(r) for r in baseline_trades) if p]

    sufficient = len(recent_prices) >= MIN_TRADE_SAMPLE and len(baseline_prices) >= MIN_TRADE_SAMPLE
    regulated = is_regulated_area("서울특별시", name)

    if not sufficient:
        return DistrictMomentum(
            code=code,
            name=name,
            recent_sample=len(recent_prices),
            baseline_sample=len(baseline_prices),
            sufficient_sample=False,
            regulated=regulated,
        )

    recent_median = statistics.median(recent_prices)
    baseline_median = statistics.median(baseline_prices)
    pct_change = ((recent_median - baseline_median) / baseline_median) * 100

    jeonse_ratio = None
    if rent_client is not None:
        recent_rents = _fetch_months(rent_client.fetch_rents, code, recent_months)
        jeonse_prices = [
            p for p in (deposit_per_area(r) for r in recent_rents if is_jeonse(r)) if p
        ]
        if len(jeonse_prices) >= MIN_JEONSE_SAMPLE:
            jeonse_ratio = (statistics.median(jeonse_prices) / recent_median) * 100

    return DistrictMomentum(
        code=code,
        name=name,
        recent_sample=len(recent_prices),
        baseline_sample=len(baseline_prices),
        sufficient_sample=True,
        pct_change=round(pct_change, 2),
        jeonse_ratio=round(jeonse_ratio, 1) if jeonse_ratio is not None else None,
        regulated=regulated,
    )


def screen_districts(
    trade_client: Any,
    rent_client: Any = None,
    districts: list[tuple[str, str]] | None = None,
    reference_date: date | None = None,
) -> list[DistrictMomentum]:
    """지역 목록을 조회해 최근 가격 모멘텀이 강한 순으로 정렬해 반환한다.

    표본이 부족한(sufficient_sample=False) 지역은 순위 매기지 않고 목록
    맨 뒤로 보낸다 (추측성 순위를 만들지 않기 위함)."""
    targets = districts if districts is not None else SEOUL_DISTRICTS

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_DISTRICTS) as executor:
        futures = [
            executor.submit(
                compute_district_momentum, trade_client, rent_client, code, name, reference_date
            )
            for code, name in targets
        ]
        results = [future.result() for future in futures]

    def sort_key(item: DistrictMomentum) -> tuple[int, float]:
        if not item.sufficient_sample:
            return (1, 0.0)
        return (0, -(item.pct_change or 0.0))

    return sorted(results, key=sort_key)
