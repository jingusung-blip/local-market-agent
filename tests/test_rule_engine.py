import unittest

from market_agent.agent import resolve_target
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


if __name__ == "__main__":
    unittest.main()
