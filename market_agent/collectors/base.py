from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from market_agent.models import EvidenceItem, GeoPoint


@dataclass(frozen=True)
class CollectContext:
    address: str
    radius_km: float
    apartment_name: str | None = None
    location: GeoPoint | None = None

    @property
    def target_text(self) -> str:
        if self.apartment_name:
            return f"{self.address} {self.apartment_name}"
        return self.address

    @property
    def region_tokens(self) -> list[str]:
        """Region names (시/도, 시/군/구, 읍/면/동) known from geocoding, used to
        keep keyword search results tied to the right place (e.g. avoid mixing
        up an apartment named "자이" in a different city)."""
        if not self.location:
            return []
        return [
            token
            for token in (
                self.location.region_1depth,
                self.location.region_2depth,
                self.location.region_3depth,
            )
            if token
        ]

    @property
    def sigungu_code(self) -> str | None:
        if not self.location:
            return None
        return self.location.sigungu_code


class Collector(Protocol):
    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        ...
