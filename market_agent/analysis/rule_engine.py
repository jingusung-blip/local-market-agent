from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from market_agent.models import (
    AnalysisReport,
    AnalysisSignal,
    EvidenceItem,
    GeoPoint,
)


def build_report(
    address: str,
    radius_km: float,
    location: GeoPoint | None,
    evidence: list[EvidenceItem],
    limitations: list[str] | None = None,
) -> AnalysisReport:
    score = calculate_score(evidence)
    outlook = outlook_label(score)
    confidence = calculate_confidence(evidence, location)

    good_news = signals_from_evidence(
        [item for item in evidence if item.sentiment == "positive" and item.category != "amenity"]
    )
    bad_news = signals_from_evidence(
        [item for item in evidence if item.sentiment == "negative" or item.category == "risk"]
    )
    policy_signals = signals_from_evidence(
        [item for item in evidence if item.category == "policy"]
    )
    local_factors = signals_from_evidence(
        [item for item in evidence if item.category == "amenity"]
    )

    summary = make_summary(score, outlook, good_news, bad_news, policy_signals, local_factors)
    report_limitations = list(limitations or [])
    if not location:
        report_limitations.append(
            "위치 좌표가 없어 실제 반경 기반 생활 인프라 수집은 제한되었습니다."
        )
    if not any(item.category in {"news", "policy"} for item in evidence):
        report_limitations.append(
            "뉴스/정책 검색 결과가 없어 공개 이슈 반영이 제한적입니다."
        )
    if any(item.source == "Demo" for item in evidence):
        report_limitations.append("API 키 없이 생성한 데모 데이터가 포함되어 있습니다.")

    return AnalysisReport(
        address=address,
        radius_km=radius_km,
        location=location,
        score=score,
        price_outlook=outlook,
        confidence=confidence,
        summary=summary,
        good_news=good_news,
        bad_news=bad_news,
        policy_signals=policy_signals,
        local_factors=local_factors,
        evidence=evidence,
        limitations=dedupe(report_limitations),
    )


def calculate_score(evidence: list[EvidenceItem]) -> int:
    if not evidence:
        return 50

    weighted_total = 0.0
    for item in evidence:
        weighted_total += item.impact * max(0.1, min(item.reliability, 1.0))

    score = 50 + weighted_total
    return int(round(max(0, min(100, score))))


def calculate_confidence(evidence: list[EvidenceItem], location: GeoPoint | None) -> float:
    confidence = 0.18
    confidence += min(0.3, len(evidence) * 0.015)
    if location:
        confidence += 0.18
    if any(item.category == "policy" for item in evidence):
        confidence += 0.12
    if any(item.category == "news" for item in evidence):
        confidence += 0.12
    if any(item.category == "amenity" for item in evidence):
        confidence += 0.10
    if any(item.source == "Demo" for item in evidence):
        confidence -= 0.18
    return round(max(0.05, min(0.9, confidence)), 2)


def outlook_label(score: int) -> str:
    if score >= 70:
        return "상승 우호 신호 강함"
    if score >= 58:
        return "완만한 상승 우호"
    if score >= 43:
        return "중립 또는 혼재"
    if score >= 32:
        return "하방 리스크 우세"
    return "주의 필요"


def signals_from_evidence(items: list[EvidenceItem], limit: int = 5) -> list[AnalysisSignal]:
    grouped: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in items:
        key = item.tags[0] if item.tags else item.category
        grouped[key].append(item)

    signals: list[AnalysisSignal] = []
    for name, group in grouped.items():
        impact = round(sum(item.impact * item.reliability for item in group), 2)
        confidence = round(min(0.9, 0.35 + len(group) * 0.08 + average_reliability(group) * 0.25), 2)
        sentiment = strongest_sentiment(group)
        top = sorted(group, key=evidence_priority, reverse=True)[0]
        urls = [item.url for item in group if item.url][:3]
        signals.append(
            AnalysisSignal(
                name=name,
                sentiment=sentiment,
                impact=impact,
                confidence=confidence,
                rationale=f"{top.title}: {top.summary}".strip(),
                evidence_urls=urls,
            )
        )

    return sorted(signals, key=lambda signal: abs(signal.impact), reverse=True)[:limit]


def strongest_sentiment(items: list[EvidenceItem]) -> str:
    total = sum(item.impact for item in items)
    if total > 0.6:
        return "positive"
    if total < -0.6:
        return "negative"
    return "mixed"


def average_reliability(items: list[EvidenceItem]) -> float:
    if not items:
        return 0.0
    return sum(item.reliability for item in items) / len(items)


def make_summary(
    score: int,
    outlook: str,
    good_news: list[AnalysisSignal],
    bad_news: list[AnalysisSignal],
    policy_signals: list[AnalysisSignal],
    local_factors: list[AnalysisSignal],
) -> str:
    positive_count = len(good_news) + len(local_factors)
    risk_count = len(bad_news)
    policy_count = len(policy_signals)
    return (
        f"종합 점수는 {score}점, 전망은 '{outlook}'입니다. "
        f"상승 신호 {positive_count}개, 리스크 {risk_count}개, 정책 변수 {policy_count}개를 반영했습니다."
    )


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def evidence_priority(item: EvidenceItem) -> tuple[datetime, float]:
    return (
        parse_evidence_date(item.published_at) or datetime.min.replace(tzinfo=timezone.utc),
        abs(item.impact) * item.reliability,
    )


def parse_evidence_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
