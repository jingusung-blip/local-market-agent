from __future__ import annotations

from market_agent.analysis.openai_analyzer import OpenAIReportAnalyzer
from market_agent.analysis.rule_engine import build_report
from market_agent.collectors.base import CollectContext
from market_agent.collectors.demo import DemoCollector
from market_agent.collectors.kakao_places import KakaoAmenityCollector
from market_agent.collectors.naver import NaverNewsPolicyCollector, NaverSearchClient
from market_agent.config import Settings
from market_agent.geo import KakaoLocalClient
from market_agent.models import AnalysisReport, AnalysisRequest, EvidenceItem, GeoPoint


class LocalMarketAgent:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    def analyze(self, request: AnalysisRequest) -> AnalysisReport:
        radius = validate_radius(request.radius_km)
        location, limitations = self._geocode(request.address, request.offline)
        context = CollectContext(
            address=request.address,
            radius_km=radius,
            apartment_name=request.apartment_name,
            location=location,
        )

        evidence = self._collect(context, request.offline)
        report = build_report(
            address=request.address,
            radius_km=radius,
            location=location,
            evidence=evidence,
            limitations=limitations,
        )

        if self.settings.openai_enabled and not request.offline:
            try:
                report = OpenAIReportAnalyzer(self.settings).enhance(report)
            except Exception as exc:  # Keep the rule-based report usable.
                report.limitations.append(f"OpenAI 분석 코멘트 생성 실패: {exc}")

        return report

    def _geocode(self, address: str, offline: bool) -> tuple[GeoPoint | None, list[str]]:
        if offline:
            return None, ["오프라인 모드라 주소 좌표화를 건너뛰었습니다."]
        if not self.settings.kakao_enabled:
            return None, ["KAKAO_REST_API_KEY가 없어 주소 좌표화를 건너뛰었습니다."]

        try:
            point = KakaoLocalClient(self.settings.kakao_rest_api_key or "").geocode(address)
        except Exception as exc:
            return None, [f"카카오 주소 좌표화 실패: {exc}"]

        if not point:
            return None, ["카카오 주소 검색 결과가 없습니다. 도로명주소나 지번주소를 더 구체적으로 입력하세요."]
        return point, []

    def _collect(self, context: CollectContext, offline: bool) -> list[EvidenceItem]:
        if offline or not (self.settings.kakao_enabled or self.settings.naver_enabled):
            return DemoCollector().collect(context)

        evidence: list[EvidenceItem] = []

        if self.settings.kakao_enabled and context.location:
            try:
                kakao_client = KakaoLocalClient(self.settings.kakao_rest_api_key or "")
                evidence.extend(KakaoAmenityCollector(kakao_client).collect(context))
            except Exception as exc:
                evidence.append(
                    EvidenceItem(
                        title="카카오 반경 시설 수집 실패",
                        summary=str(exc),
                        source="System",
                        category="risk",
                        sentiment="negative",
                        reliability=0.2,
                        impact=-0.4,
                    )
                )

        if self.settings.naver_enabled:
            try:
                naver_client = NaverSearchClient(
                    self.settings.naver_client_id or "",
                    self.settings.naver_client_secret or "",
                )
                evidence.extend(NaverNewsPolicyCollector(naver_client).collect(context))
            except Exception as exc:
                evidence.append(
                    EvidenceItem(
                        title="네이버 뉴스/정책 수집 실패",
                        summary=str(exc),
                        source="System",
                        category="risk",
                        sentiment="negative",
                        reliability=0.2,
                        impact=-0.5,
                    )
                )

        return evidence


def validate_radius(radius_km: float) -> float:
    if radius_km < 2 or radius_km > 5:
        raise ValueError("반경은 2km 이상 5km 이하로 입력해야 합니다.")
    return round(radius_km, 2)
