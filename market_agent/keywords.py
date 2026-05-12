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


def classify_sentiment(text: str, default: str = "neutral") -> tuple[str, list[str]]:
    positives = keyword_hits(text, POSITIVE_KEYWORDS)
    negatives = keyword_hits(text, NEGATIVE_KEYWORDS)
    policies = keyword_hits(text, POLICY_KEYWORDS)

    if positives and negatives:
        sentiment = "mixed"
    elif positives:
        sentiment = "positive"
    elif negatives:
        sentiment = "negative"
    else:
        sentiment = default

    return sentiment, sorted(set(positives + negatives + policies))


def estimate_impact(text: str, category: str, default_sentiment: str = "neutral") -> float:
    sentiment, tags = classify_sentiment(text, default_sentiment)
    base = 0.0
    if sentiment == "positive":
        base = 2.5
    elif sentiment == "negative":
        base = -2.8
    elif sentiment == "mixed":
        base = 0.4

    if category == "policy":
        base *= 1.25
    elif category == "amenity":
        base *= 0.75
    elif category == "news":
        base *= 1.0

    if "확정" in tags or "개통" in tags or "착공" in tags:
        base += 1.2
    if "지연" in tags or "취소" in tags or "무산" in tags:
        base -= 1.5

    return round(max(-6.0, min(6.0, base)), 2)
