from __future__ import annotations

from market_agent.collectors.base import CollectContext
from market_agent.geo import KakaoLocalClient
from market_agent.models import EvidenceItem


CATEGORY_GROUPS = {
    "SW8": ("지하철역", 2.8),
    "SC4": ("학교", 1.5),
    "HP8": ("병원", 1.2),
    "MT1": ("대형마트", 0.9),
    "CT1": ("문화시설", 0.8),
}


class KakaoAmenityCollector:
    def __init__(self, client: KakaoLocalClient) -> None:
        self.client = client

    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        if not context.location:
            return []

        radius_m = int(context.radius_km * 1000)
        evidence: list[EvidenceItem] = []
        for category_code, (label, weight) in CATEGORY_GROUPS.items():
            places = self.client.search_category(
                category_code, context.location, radius_m=radius_m, size=15
            )
            if not places:
                continue

            nearest = places[:5]
            nearest_names = [
                f"{place.get('place_name')}({round(float(place.get('distance', 0)) / 1000, 2)}km)"
                for place in nearest
            ]
            count = len(places)
            impact = min(5.0, weight + max(0, count - 1) * 0.25)
            evidence.append(
                EvidenceItem(
                    title=f"반경 {context.radius_km:g}km 내 {label} {count}곳 탐지",
                    summary=", ".join(nearest_names),
                    source="Kakao Local",
                    category="amenity",
                    sentiment="positive",
                    distance_km=round(float(nearest[0].get("distance", 0)) / 1000, 2),
                    reliability=0.82,
                    impact=round(impact, 2),
                    tags=[label, "생활인프라"],
                )
            )

        return evidence
