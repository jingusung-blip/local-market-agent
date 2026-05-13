import unittest
from datetime import datetime, timezone
from email.utils import format_datetime

from market_agent.agent import friendly_ai_error_message, resolve_target
from market_agent.analysis.rule_engine import build_report
from market_agent.models import EvidenceItem


class RuleEngineTests(unittest.TestCase):
    def test_positive_evidence_raises_outlook_score(self) -> None:
        empty_report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[],
        )
        report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[
                EvidenceItem(
                    title="교통 호재 확정",
                    summary="지하철 개통 확정",
                    source="test",
                    category="news",
                    sentiment="positive",
                    reliability=0.8,
                    impact=5,
                    tags=["교통"],
                )
            ],
        )

        self.assertGreater(report.score, empty_report.score)
        self.assertTrue(report.good_news)

    def test_negative_evidence_lowers_outlook_score(self) -> None:
        report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[
                EvidenceItem(
                    title="침수 리스크",
                    summary="저지대 침수 민원",
                    source="test",
                    category="risk",
                    sentiment="negative",
                    reliability=0.8,
                    impact=-5,
                    tags=["침수"],
                )
            ],
        )

        self.assertLess(report.score, 50)
        self.assertTrue(report.bad_news)

    def test_amenity_only_evidence_is_capped_for_investment_score(self) -> None:
        report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[
                EvidenceItem(
                    title=f"생활 인프라 {index}",
                    summary="주변 생활 편의시설",
                    source="test",
                    category="amenity",
                    sentiment="positive",
                    reliability=0.82,
                    impact=5,
                    tags=["생활인프라"],
                )
                for index in range(5)
            ],
        )

        self.assertLess(report.score, 58)
        self.assertEqual(report.price_outlook, "중립 또는 추가 검증")

    def test_high_score_requires_more_than_positive_amenities(self) -> None:
        report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[
                EvidenceItem(
                    title="생활 인프라 풍부",
                    summary="편의시설이 많음",
                    source="test",
                    category="amenity",
                    sentiment="positive",
                    reliability=0.9,
                    impact=5,
                    tags=["생활인프라"],
                ),
                EvidenceItem(
                    title="교통 호재 확정",
                    summary="지하철 개통 확정",
                    source="test",
                    category="news",
                    sentiment="positive",
                    reliability=0.9,
                    impact=5,
                    tags=["교통"],
                ),
            ],
        )

        self.assertLess(report.score, 63)

    def test_strong_outlook_requires_diverse_positive_signals_with_risk_scan(self) -> None:
        report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[
                EvidenceItem(
                    title="교통 호재 확정",
                    summary="지하철 개통 확정",
                    source="test",
                    category="news",
                    sentiment="positive",
                    reliability=0.9,
                    impact=6,
                    tags=["교통"],
                ),
                EvidenceItem(
                    title="업무지구 개발",
                    summary="일자리 개발 호재",
                    source="test",
                    category="news",
                    sentiment="positive",
                    reliability=0.9,
                    impact=6,
                    tags=["일자리"],
                ),
                EvidenceItem(
                    title="복합개발 착공",
                    summary="복합개발 착공",
                    source="test",
                    category="news",
                    sentiment="positive",
                    reliability=0.9,
                    impact=6,
                    tags=["개발"],
                ),
                EvidenceItem(
                    title="정비사업 고시",
                    summary="정비구역 고시",
                    source="test",
                    category="policy",
                    sentiment="positive",
                    reliability=0.9,
                    impact=7,
                    tags=["정비구역"],
                ),
                EvidenceItem(
                    title="공공 교통 계획",
                    summary="지자체 교통 계획",
                    source="test",
                    category="policy",
                    sentiment="positive",
                    reliability=0.9,
                    impact=7,
                    tags=["지자체"],
                ),
                EvidenceItem(
                    title="생활 인프라 풍부",
                    summary="반복 이용 시설이 많음",
                    source="test",
                    category="amenity",
                    sentiment="positive",
                    reliability=0.9,
                    impact=5,
                    tags=["생활인프라"],
                ),
                EvidenceItem(
                    title="대형 생활 편의시설",
                    summary="편의시설 접근성 양호",
                    source="test",
                    category="amenity",
                    sentiment="positive",
                    reliability=0.9,
                    impact=5,
                    tags=["생활인프라"],
                ),
                EvidenceItem(
                    title="교통 생활권",
                    summary="역 접근성 양호",
                    source="test",
                    category="amenity",
                    sentiment="positive",
                    reliability=0.9,
                    impact=5,
                    tags=["생활인프라"],
                ),
                EvidenceItem(
                    title="소음 점검 필요",
                    summary="일부 생활 소음 민원 가능성",
                    source="test",
                    category="risk",
                    sentiment="negative",
                    reliability=0.4,
                    impact=-1,
                    tags=["소음"],
                ),
            ],
        )

        self.assertGreaterEqual(report.score, 72)
        self.assertEqual(report.price_outlook, "상승 우호 신호 강함")

    def test_resolve_target_allows_apartment_only(self) -> None:
        self.assertEqual(resolve_target("", "헬리오시티"), "헬리오시티")

    def test_friendly_ai_rate_limit_message_hides_raw_error(self) -> None:
        message = friendly_ai_error_message(Exception("Error code: 429 - rate_limit_exceeded"))

        self.assertIn("OpenAI 사용량 제한", message)
        self.assertNotIn("rate_limit_exceeded", message)

    def test_signal_rationale_prefers_newer_evidence(self) -> None:
        old_date = format_datetime(datetime(2024, 1, 1, tzinfo=timezone.utc), usegmt=True)
        new_date = format_datetime(datetime(2026, 5, 1, tzinfo=timezone.utc), usegmt=True)
        report = build_report(
            address="서울시 테스트로 1",
            radius_km=3,
            location=None,
            evidence=[
                EvidenceItem(
                    title="오래된 교통 호재",
                    summary="영향은 크지만 오래된 기사",
                    source="test",
                    category="news",
                    sentiment="positive",
                    published_at=old_date,
                    reliability=0.9,
                    impact=5,
                    tags=["교통"],
                ),
                EvidenceItem(
                    title="최신 교통 호재",
                    summary="최근 기사",
                    source="test",
                    category="news",
                    sentiment="positive",
                    published_at=new_date,
                    reliability=0.7,
                    impact=2,
                    tags=["교통"],
                ),
            ],
        )

        self.assertIn("최신 교통 호재", report.good_news[0].rationale)


if __name__ == "__main__":
    unittest.main()
