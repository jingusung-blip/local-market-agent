from __future__ import annotations

from market_agent.collectors.base import CollectContext
from market_agent.models import EvidenceItem


class DemoCollector:
    """Offline sample data so the product flow can be tested without API keys."""

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        target = context.apartment_name or context.address
        return [
            EvidenceItem(
                title=f"{target} 인근 교통 개선 기대",
                summary="반경 내 교통 접근성 개선 이슈가 있다고 가정한 데모 데이터입니다.",
                source="Demo",
                category="news",
                sentiment="positive",
                reliability=0.35,
                impact=2.4,
                tags=["교통", "호재"],
            ),
            EvidenceItem(
                title=f"{target} 주변 정비사업 추진 검토",
                summary="지자체 도시계획과 정비사업 가능성을 점검해야 한다는 데모 정책 신호입니다.",
                source="Demo",
                category="policy",
                sentiment="mixed",
                reliability=0.35,
                impact=1.2,
                tags=["지자체", "정비사업"],
            ),
            EvidenceItem(
                title=f"{target} 생활 소음 민원 가능성",
                summary="상권 밀집지나 대로변 입지에서는 소음/혼잡 리스크를 따로 검증해야 합니다.",
                source="Demo",
                category="risk",
                sentiment="negative",
                reliability=0.35,
                impact=-1.8,
                tags=["소음", "민원"],
            ),
        ]
