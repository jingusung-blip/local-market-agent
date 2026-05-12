from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


Sentiment = Literal["positive", "negative", "neutral", "mixed"]


@dataclass
class GeoPoint:
    address: str
    latitude: float
    longitude: float
    source: str = "kakao"


@dataclass
class EvidenceItem:
    title: str
    summary: str
    source: str
    category: str
    sentiment: Sentiment = "neutral"
    url: str | None = None
    published_at: str | None = None
    distance_km: float | None = None
    reliability: float = 0.5
    impact: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class AnalysisSignal:
    name: str
    sentiment: Sentiment
    impact: float
    confidence: float
    rationale: str
    evidence_urls: list[str] = field(default_factory=list)


@dataclass
class AnalysisRequest:
    address: str = ""
    radius_km: float = 3.0
    apartment_name: str | None = None
    offline: bool = False


@dataclass
class AnalysisReport:
    address: str
    radius_km: float
    location: GeoPoint | None
    score: int
    price_outlook: str
    confidence: float
    summary: str
    good_news: list[AnalysisSignal]
    bad_news: list[AnalysisSignal]
    policy_signals: list[AnalysisSignal]
    local_factors: list[AnalysisSignal]
    evidence: list[EvidenceItem]
    limitations: list[str]
    llm_commentary: str | None = None
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
