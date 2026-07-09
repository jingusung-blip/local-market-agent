from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Any, ClassVar

from market_agent.collectors.base import CollectContext
from market_agent.models import EvidenceItem


KEY_STATISTIC_NAME = "한국은행 기준금리"


class EcosApiError(RuntimeError):
    pass


class EcosClient:
    """한국은행 ECOS Open API 클라이언트.

    "100대 통계지표(KeyStatisticList)" 서비스를 사용한다. 국토부 실거래가
    API 때는 통계표코드/필드명을 문서만 보고 추측하다가 실제로 두 번 틀렸는데,
    이 서비스는 통계표코드를 몰라도 되는 사전 정의된 100개 핵심 지표를
    이름("한국은행 기준금리")으로 바로 찾을 수 있어 그런 종류의 추측 리스크가
    없다. 실제 sample 엔드포인트로 응답 스키마(KeyStatisticList.row[].{
    CLASS_NAME, KEYSTAT_NAME, DATA_VALUE, CYCLE, UNIT_NAME})와 에러 형식
    ({"RESULT": {"CODE", "MESSAGE"}})을 확인했다 (2026-07-09).

    Docs: https://ecos.bok.or.kr/api/
    """

    base_url = "https://ecos.bok.or.kr/api/KeyStatisticList"

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def fetch_key_statistics(self, count: int = 100) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{self.api_key}/json/kr/1/{count}"
        request = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise EcosApiError(f"ECOS API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise EcosApiError(f"ECOS API request failed: {exc}") from exc

        return parse_key_statistic_response(payload)


def parse_key_statistic_response(payload: bytes) -> list[dict[str, Any]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise EcosApiError(f"ECOS API returned invalid JSON: {exc}") from exc

    if "RESULT" in data:
        result = data["RESULT"]
        raise EcosApiError(f"ECOS API error {result.get('CODE')}: {result.get('MESSAGE')}")

    body = data.get("KeyStatisticList") or {}
    return body.get("row", [])


def find_base_rate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if row.get("KEYSTAT_NAME") == KEY_STATISTIC_NAME:
            return row
    return None


def build_base_rate_evidence(row: dict[str, Any] | None) -> list[EvidenceItem]:
    if not row:
        return []

    value = row.get("DATA_VALUE", "?")
    cycle = row.get("CYCLE", "")
    unit = row.get("UNIT_NAME", "%")

    return [
        EvidenceItem(
            title=f"한국은행 기준금리 {value}{unit} (기준 {cycle})",
            summary=(
                f"한국은행이 발표하는 기준금리는 현재 {value}{unit}입니다 ({cycle} 기준). "
                "특정 단지에 국한된 신호가 아니라 전국 공통 거시 변수이며, 금리가 낮을수록 "
                "대출 부담이 줄어 매수 여력에 우호적이고, 높을수록 그 반대로 작용하는 경향이 "
                "있습니다. 참고용 맥락 정보로만 반영했고 점수 계산에는 영향을 주지 않습니다."
            ),
            source="ECOS",
            category="policy",
            sentiment="neutral",
            reliability=0.95,
            impact=0.0,
            tags=["기준금리"],
        )
    ]


class BaseRateCollector:
    """전국 공통 거시 변수라 위치와 무관하게 하루 한 번만 조회하면 충분하므로
    프로세스 단위(모듈 레벨)로 하루치 캐시를 둔다."""

    _cache: ClassVar[dict[str, Any]] = {}

    def __init__(self, client: EcosClient) -> None:
        self.client = client

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        today = date.today().isoformat()
        cached = BaseRateCollector._cache
        if cached.get("date") == today:
            return build_base_rate_evidence(cached.get("row"))

        rows = self.client.fetch_key_statistics(count=100)
        row = find_base_rate(rows)
        BaseRateCollector._cache = {"date": today, "row": row}
        return build_base_rate_evidence(row)
