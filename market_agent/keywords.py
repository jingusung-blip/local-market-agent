from __future__ import annotations

import re


POSITIVE_KEYWORDS = {
    "개발",
    "호재",
    "교통",
    "역세권",
    "GTX",
    "지하철",
    "철도",
    "복합개발",
    "재개발",
    "재건축",
    "정비사업",
    "학군",
    "학교",
    "공원",
    "상권",
    "업무지구",
    "산업단지",
    "일자리",
    "착공",
    "개통",
    "확정",
    "유치",
}

NEGATIVE_KEYWORDS = {
    "침수",
    "화재",
    "사고",
    "소음",
    "악취",
    "폐기물",
    "공장",
    "민원",
    "분쟁",
    "반대",
    "지연",
    "무산",
    "취소",
    "규제",
    "하락",
    "공급과잉",
    "미분양",
    "범죄",
    "노후",
}

POLICY_KEYWORDS = {
    "정부",
    "지자체",
    "시청",
    "구청",
    "도시계획",
    "지구단위계획",
    "공공주택",
    "공시지가",
    "분양가",
    "대출",
    "세제",
    "규제지역",
    "정비구역",
    "고시",
    "공고",
}

# Words that, when found close to a negative keyword, mean the risk is being
# resolved/reduced/denied rather than confirmed (e.g. "침수 우려 해소",
# "소음 민원 없음", "규제 완화"). Without this, plain substring matching
# would score these as bad news even though the article is reassuring.
NEGATION_FLIP_MARKERS = {
    "해소",
    "완화",
    "해제",
    "축소",
    "감소",
    "줄어",
    "없음",
    "없다",
    "없어",
    "아니다",
    "아닌",
    "무관",
    "우려 낮",
    "가능성 낮",
    "예방",
    "정상화",
}

# Redevelopment/reconstruction progresses through stages with very different
# certainty and price-relevant weight. A "조합설립" stage project can still
# fall through; "착공" or "준공" is close to guaranteed delivery. Treating
# every "재건축/재개발/정비사업" mention the same (as the previous version did)
# overstates early-stage, uncertain projects.
REDEVELOPMENT_STAGE_WEIGHTS: dict[str, float] = {
    "정비구역 지정": 0.55,
    "정비구역지정": 0.55,
    "추진위원회": 0.55,
    "조합설립": 0.7,
    "조합설립인가": 0.7,
    "사업시행인가": 0.85,
    "관리처분인가": 1.0,
    "이주": 1.05,
    "철거": 1.05,
    "착공": 1.2,
    "준공": 1.3,
    "입주": 1.3,
}
REDEVELOPMENT_TRIGGER_TAGS = {"재건축", "재개발", "정비사업", "정비구역"}

NEGATION_WINDOW = 10


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def keyword_hits(text: str, keywords: set[str]) -> list[str]:
    upper_text = text.upper()
    hits: list[str] = []
    for keyword in keywords:
        candidate = keyword.upper()
        if candidate in upper_text:
            hits.append(keyword)
    return sorted(hits)


def _keyword_positions(text: str, keyword: str) -> list[int]:
    upper_text = text.upper()
    candidate = keyword.upper()
    positions = []
    start = 0
    while True:
        idx = upper_text.find(candidate, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + len(candidate)
    return positions


def _is_negated(text: str, keyword: str, window: int = NEGATION_WINDOW) -> bool:
    """True if a flip marker appears within `window` characters of any
    occurrence of `keyword`, meaning the risk is being denied/resolved."""
    upper_text = text.upper()
    for pos in _keyword_positions(text, keyword):
        segment = upper_text[max(0, pos - window) : pos + len(keyword) + window]
        for marker in NEGATION_FLIP_MARKERS:
            if marker.upper() in segment:
                return True
    return False


def classify_sentiment(text: str, default: str = "neutral") -> tuple[str, list[str]]:
    positives = keyword_hits(text, POSITIVE_KEYWORDS)
    raw_negatives = keyword_hits(text, NEGATIVE_KEYWORDS)
    policies = keyword_hits(text, POLICY_KEYWORDS)

    negatives = [word for word in raw_negatives if not _is_negated(text, word)]
    mitigated = [word for word in raw_negatives if word not in negatives]

    if positives and negatives:
        sentiment = "mixed"
    elif positives:
        sentiment = "positive"
    elif negatives:
        sentiment = "negative"
    elif mitigated:
        # A risk keyword was present but flagged as resolved/denied in context.
        sentiment = "neutral"
    else:
        sentiment = default

    # Tags reflect *what was mentioned* (including mitigated risk keywords, so
    # the report can still surface "침수 우려 해소" as a topic), while
    # `sentiment` reflects the net read after negation handling.
    tags = sorted(set(positives + raw_negatives + policies))
    return sentiment, tags


def redevelopment_stage_multiplier(text: str, tags: list[str]) -> float:
    """Return the weight of the most advanced redevelopment/reconstruction
    stage mentioned in the text. 1.0 (no change) if the item is not actually
    about a redevelopment/reconstruction project."""
    if not REDEVELOPMENT_TRIGGER_TAGS.intersection(tags):
        return 1.0

    upper_text = text.upper()
    best = None
    for stage_keyword, weight in REDEVELOPMENT_STAGE_WEIGHTS.items():
        if stage_keyword.upper() in upper_text:
            if best is None or weight > best:
                best = weight
    return best if best is not None else 0.55  # mentioned but stage unclear -> early/uncertain


def estimate_impact(text: str, category: str, default_sentiment: str = "neutral") -> float:
    sentiment, tags = classify_sentiment(text, default_sentiment)

    positive_hits = keyword_hits(text, POSITIVE_KEYWORDS)
    negative_hits = [word for word in keyword_hits(text, NEGATIVE_KEYWORDS) if not _is_negated(text, word)]

    if sentiment == "positive":
        # More distinct positive signals in one article/notice raises
        # conviction, but with diminishing returns instead of a flat constant.
        base = 1.8 + 0.35 * max(0, len(positive_hits) - 1)
    elif sentiment == "negative":
        base = -2.0 - 0.4 * max(0, len(negative_hits) - 1)
    elif sentiment == "mixed":
        base = 0.4
    else:
        base = 0.0

    if category == "policy":
        base *= 1.25
    elif category == "amenity":
        base *= 0.75
    elif category == "news":
        base *= 1.0

    if "확정" in tags or "개통" in tags or "착공" in tags:
        base += 1.2
    # Use the negation-filtered hits here (not raw tags) so a mitigated risk
    # like "지연 우려 해소" doesn't still get penalized as if it were live.
    if any(word in negative_hits for word in ("지연", "취소", "무산")):
        base -= 1.5

    base *= redevelopment_stage_multiplier(text, tags)

    return round(max(-6.0, min(6.0, base)), 2)
