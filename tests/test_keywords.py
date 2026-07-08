import unittest

from market_agent.keywords import (
    classify_sentiment,
    estimate_impact,
    is_tag_list_text,
    redevelopment_stage_multiplier,
)


class KeywordsTests(unittest.TestCase):
    def test_negation_flip_turns_risk_keyword_neutral(self) -> None:
        sentiment, tags = classify_sentiment("이 지역은 침수 우려가 해소되었다는 발표가 있었습니다.")
        self.assertEqual(sentiment, "neutral")
        self.assertIn("침수", tags)

    def test_plain_negative_keyword_without_flip_marker_stays_negative(self) -> None:
        sentiment, _ = classify_sentiment("이 지역은 침수 피해가 반복되고 있습니다.")
        self.assertEqual(sentiment, "negative")

    def test_more_positive_hits_increase_impact_magnitude(self) -> None:
        single = estimate_impact("교통 개발 이슈", "news", "positive")
        multiple = estimate_impact("교통 개발 역세권 호재 확정", "news", "positive")
        self.assertGreater(multiple, single)

    def test_redevelopment_stage_multiplier_scales_with_progress(self) -> None:
        early = redevelopment_stage_multiplier("조합설립 단계인 재건축 사업", ["재건축"])
        late = redevelopment_stage_multiplier("착공에 들어간 재건축 사업", ["재건축"])
        self.assertLess(early, late)

    def test_redevelopment_stage_multiplier_ignores_unrelated_text(self) -> None:
        multiplier = redevelopment_stage_multiplier("착공 소식이 있는 도로 공사", [])
        self.assertEqual(multiplier, 1.0)

    def test_early_stage_redevelopment_impact_lower_than_completed(self) -> None:
        early = estimate_impact("정비구역 지정 이제 막 시작된 재건축 추진", "news", "positive")
        late = estimate_impact("착공 들어간 재건축 사업 순항", "news", "positive")
        self.assertLess(early, late)

    def test_menu_tag_list_does_not_trigger_false_negative_sentiment(self) -> None:
        # Real bug report: a real-estate blog's own nav-menu text (rendered
        # as a pipe-delimited list of topic tabs, one of which is literally
        # "미분양") got misread as an assertion that the complex has unsold
        # units, even though the article body was just a 분양공고 (sales
        # announcement) with no actual vacancy problem.
        text = (
            "고덕강일 대성베르힐: 고덕강일 대성베르힐 | 강동구 상일동 | 미분양 | "
            "위치 | 입주자모집공고 | 분양가 | 평면 | 청약 | 모델하우스"
        )
        self.assertTrue(is_tag_list_text(text))

        sentiment, tags = classify_sentiment(text, "neutral")
        self.assertEqual(sentiment, "neutral")
        self.assertNotIn("미분양", tags)
        self.assertIn("공고", tags)

        self.assertEqual(estimate_impact(text, "policy", "neutral"), 0.0)

    def test_ordinary_sentence_is_not_treated_as_tag_list(self) -> None:
        self.assertFalse(is_tag_list_text("이 지역은 미분양 물량이 늘고 있다는 우려가 나옵니다."))


if __name__ == "__main__":
    unittest.main()
