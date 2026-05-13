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
        target = resolve_target(request.address, request.apartment_name)
        location, limitations = self._geocode(target, request.offline)
        context = CollectContext(
            address=target,
            radius_km=radius,
            apartment_name=request.apartment_name,
            location=location,
        )

        evidence = self._collect(context, request.offline)
        report = build_report(
            address=target,
            radius_km=radius,
            location=location,
            evidence=evidence,
            limitations=limitations,
        )

        if self.settings.openai_enabled and not request.offline:
            try:
                report = OpenAIReportAnalyzer(self.settings).enhance(report)
            except Exception as exc:
                report.limitations.append(friendly_ai_error_message(exc))

        return report

    def _geocode(self, target: str, offline: bool) -> tuple[GeoPoint | None, list[str]]:
        if offline:
            return None, ["오프라인 모드라 실제 좌표와 반경 데이터를 조회하지 않았습니다."]
        if not self.settings.kakao_enabled:
            return None, ["카카오 API 키가 없어 좌표와 반경 데이터를 조회하지 못했습니다."]

        client = KakaoLocalClient(self.settings.kakao_rest_api_key or "")
        try:
            point = client.geocode(target)
            if not point:
                point = client.keyword_geocode(target)
        except Exception as exc:
            return None, [f"카카오 위치 조회 실패: {exc}"]

        if not point:
            return None, [
                "입력값으로 위치를 찾지 못했습니다. 도로명주소, 지번주소, 또는 단지명을 더 구체적으로 입력하세요."
            ]
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
                        title="반경 생활 인프라 수집 실패",
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
                        title="뉴스/정책 수집 실패",
                        summary=str(exc),
                        source="System",
                        category="risk",
                        sentiment="negative",
                        reliability=0.2,
                        impact=-0.5,
                    )
                )

        return evidence


def resolve_target(address: str | None, apartment_name: str | None) -> str:
    clean_address = (address or "").strip()
    clean_apartment = (apartment_name or "").strip()
    if clean_address and clean_apartment:
        return f"{clean_address} {clean_apartment}"
    if clean_address:
        return clean_address
    if clean_apartment:
        return clean_apartment
    raise ValueError("주소 또는 아파트 단지명 중 하나는 입력해야 합니다.")


def validate_radius(radius_km: float) -> float:
    if radius_km < 2 or radius_km > 5:
        raise ValueError("분석 반경은 2km 이상 5km 이하로 입력해야 합니다.")
    return round(radius_km, 2)


def friendly_ai_error_message(exc: Exception) -> str:
    text = str(exc).lower()
    error_name = type(exc).__name__.lower()
    if "429" in text or "rate_limit" in text or "ratelimit" in error_name:
        return (
            "AI 요약은 OpenAI 사용량 제한으로 잠시 생성하지 못했습니다. "
            "기본 입지 분석은 정상 처리되었고, 몇 초 뒤 다시 분석하면 요약이 붙을 수 있습니다."
        )
    if "api key" in text or "authentication" in text or "unauthorized" in text:
        return "AI 요약은 OpenAI API 키 확인이 필요해 생성하지 못했습니다. 기본 입지 분석은 정상 처리되었습니다."
    return "AI 요약은 일시적인 외부 API 문제로 생성하지 못했습니다. 기본 입지 분석은 정상 처리되었습니다."
