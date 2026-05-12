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


class Collector(Protocol):
    def collect(self, context: CollectContext) -> list[EvidenceItem]:
        ...
