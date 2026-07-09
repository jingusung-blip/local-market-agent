from __future__ import annotations

from market_agent.collectors.base import CollectContext
from market_agent.models import EvidenceItem
from market_agent.regulation_areas import LAST_UPDATED, is_regulated_area


class RegulationAreaCollector:
    """국토부 규제지역(조정대상지역/투기과열지구) 지정 여부를 수동 유지보수 목록
    (market_agent/regulation_areas.py) 기준으로 판단해 정책 evidence를 생성한다.

    공식 API가 없어 뉴스 발표를 근거로 사람이 주기적으로 갱신하는 데이터이므로,
    데이터가 오래됐을 가능성을 감안해 summary에 항상 기준일과 재확인 안내를
    포함한다. 외부 API 호출이 없어 별도 키/설정 없이 좌표만 있으면 항상 실행된다."""

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        if not context.location:
            return []

        region_1 = context.location.region_1depth
        region_2 = context.location.region_2depth

        if not region_1 and not region_2:
            return []

        regulated = is_regulated_area(region_1, region_2)
        area_label = region_2 or region_1 or "해당 지역"

        if regulated:
            return [
                EvidenceItem(
                    title=f"{area_label} 규제지역(조정대상지역·투기과열지구) 지정",
                    summary=(
                        f"{area_label}는 조정대상지역 및 투기과열지구로 지정된 상태입니다 "
                        f"(수동 갱신 목록 기준일 {LAST_UPDATED}). 대출 한도 축소, 청약 재당첨 제한, "
                        "다주택자 양도세 중과 등 규제가 적용됩니다. 공식 API가 없어 뉴스 발표를 "
                        "근거로 사람이 갱신하는 목록이니, 실제 거래 전에는 국토교통부 고시로 "
                        "최종 확인하세요."
                    ),
                    source="MOLIT-Manual",
                    category="policy",
                    sentiment="negative",
                    reliability=0.7,
                    impact=-1.5,
                    tags=["규제지역"],
                )
            ]

        return [
            EvidenceItem(
                title=f"{area_label} 규제지역 미지정",
                summary=(
                    f"{area_label}는 현재 목록 기준(기준일 {LAST_UPDATED}) 조정대상지역·"
                    "투기과열지구로 지정되어 있지 않습니다. 다만 이 목록은 수동 갱신 자료이므로 "
                    "최신 지정 여부는 국토교통부 고시로 재확인하는 것이 안전합니다."
                ),
                source="MOLIT-Manual",
                category="policy",
                sentiment="neutral",
                reliability=0.6,
                impact=0.0,
                tags=["규제지역"],
            )
        ]
