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


NO_EVIDENCE_SCORE = 45
BASE_INVESTMENT_SCORE = 48
AMENITY_POSITIVE_CAP = 5.0
NEWS_POSITIVE_CAP = 12.0
POLICY_POSITIVE_CAP = 8.0
OTHER_POSITIVE_CAP = 5.0


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
        return NO_EVIDENCE_SCORE

    positive_totals = {
        "amenity": 0.0,
        "news": 0.0,
        "policy": 0.0,
        "other": 0.0,
    }
    negative_total = 0.0
    for item in evidence:
        contribution = evidence_contribution(item)
        if contribution >= 0:
            positive_totals[score_category(item)] += contribution
        else:
            negative_total += contribution

    capped_positive_total = (
        min(AMENITY_POSITIVE_CAP, positive_totals["amenity"])
        + min(NEWS_POSITIVE_CAP, positive_totals["news"])
        + min(POLICY_POSITIVE_CAP, positive_totals["policy"])
        + min(OTHER_POSITIVE_CAP, positive_totals["other"])
    )

    score = BASE_INVESTMENT_SCORE + capped_positive_total + negative_total
    score -= uncertainty_penalty(evidence)
    score = apply_investment_caps(score, evidence)
    return int(round(max(0, min(100, score))))


def evidence_contribution(item: EvidenceItem) -> float:
    weighted = item.impact * clamp_reliability(item.reliability)
    if weighted >= 0:
        if item.category == "amenity":
            return weighted * 0.38
        if item.category == "policy":
            return weighted * 0.65
        return weighted * 0.70

    if item.category == "risk":
        return weighted * 1.35
    if item.category == "policy":
        return weighted * 1.20
    return weighted * 1.20


def score_category(item: EvidenceItem) -> str:
    if item.category in {"amenity", "news", "policy"}:
        return item.category
    return "other"


def clamp_reliability(value: float) -> float:
    return max(0.1, min(value, 1.0))


def uncertainty_penalty(evidence: list[EvidenceItem]) -> float:
    penalty = 0.0
    if len(evidence) < 4:
        penalty += 2.0
    if not any(item.category in {"news", "policy"} for item in evidence):
        penalty += 4.0
    if any(item.source == "Demo" for item in evidence):
        penalty += 3.0
    return penalty


def apply_investment_caps(score: float, evidence: list[EvidenceItem]) -> float:
    has_market_signal = any(item.category in {"news", "policy"} for item in evidence)
    has_positive_market_signal = any(
        item.category in {"news", "policy"} and evidence_contribution(item) > 0
        for item in evidence
    )
    has_policy_signal = any(item.category == "policy" for item in evidence)
    has_risk_signal = any(
        item.sentiment == "negative" or item.category == "risk" or evidence_contribution(item) < 0
        for item in evidence
    )

    if not has_market_signal:
        score = min(score, 55)
    if not has_positive_market_signal:
        score = min(score, 60)
    if not has_policy_signal:
        score = min(score, 68)
    if not has_risk_signal:
        score = min(score, 69)
    return score


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
    if score >= 72:
        return "상승 우호 신호 강함"
    if score >= 63:
        return "완만한 상승 우호"
    if score >= 46:
        return "중립 또는 추가 검증"
    if score >= 34:
        return "하방 리스크 우세"
    return "주의 필요"


def signals_from_evidence(items: list[EvidenceItem], limit: int = 5) -> list[AnalysisSignal]:
    grouped: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in items:
        key = item.tags[0] if item.tags else item.category
        grouped[key].append(item)

    signals: list[AnalysisSignal] = []
    for name, group in grouped.items():
        impact = round(sum(evidence_contribution(item) for item in group), 2)
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
        f"종합 점수는 {score}점, 보수 전망은 '{outlook}'입니다. "
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
