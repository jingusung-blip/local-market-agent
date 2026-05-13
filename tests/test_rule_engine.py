import unittest
from datetime import datetime, timezone
from email.utils import format_datetime

from market_agent.agent import friendly_ai_error_message, resolve_target
from market_agent.analysis.rule_engine import build_report
from market_agent.models import EvidenceItem


class RuleEngineTests(unittest.TestCase):
    def test_positive_evidence_raises_outlook_score(self) -> None:
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

        self.assertGreater(report.score, 50)
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
