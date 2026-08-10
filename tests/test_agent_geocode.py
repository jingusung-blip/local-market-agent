import unittest
from unittest.mock import patch

from market_agent.agent import LocalMarketAgent
from market_agent.config import Settings
from market_agent.models import AnalysisRequest, GeoPoint


class FuzzyOnlyKakaoClient:
    """Exact address search always misses; keyword search always hits (loosely)."""

    def __init__(self, rest_api_key: str) -> None:
        pass

    def geocode(self, address: str) -> GeoPoint | None:
        return None

    def keyword_geocode(self, query: str) -> GeoPoint | None:
        return GeoPoint(
            address="서울시 엉뚱동 123 (느슨하게 매칭된 장소)",
            latitude=37.5,
            longitude=127.0,
            source="kakao-keyword",
        )


class GeocodeFallbackTests(unittest.TestCase):
    def _settings(self) -> Settings:
        return Settings(kakao_rest_api_key="fake-key")

    @patch("market_agent.agent.KakaoLocalClient", FuzzyOnlyKakaoClient)
    def test_keyword_fallback_warns_about_loose_match_in_limitations(self) -> None:
        # Regression test (2026-08-10 실사용 피드백): 존재하지 않는 주소를
        # 입력해도 카카오 키워드 검색으로 엉뚱한 장소가 매칭되면 사용자에게
        # 아무 경고 없이 정상 분석처럼 보였다. 이제는 느슨한 매칭으로
        # 위치를 추정했을 때 limitations에 반드시 안내가 남아야 한다.
        agent = LocalMarketAgent(settings=self._settings())

        report = agent.analyze(
            AnalysisRequest(address="존재하지않는가짜주소 999", offline=False)
        )

        self.assertTrue(
            any("느슨한" in item or "가장 비슷한 장소명" in item for item in report.limitations)
        )


if __name__ == "__main__":
    unittest.main()
