from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from market_agent.config import Settings
from market_agent.models import AnalysisReport


class OpenAIReportAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enhance(self, report: AnalysisReport) -> AnalysisReport:
        if not self.settings.openai_enabled:
            return report

        try:
            import truststore

            truststore.inject_into_ssl()
        except Exception:
            pass

        from openai import OpenAI

        kwargs = {"api_key": self.settings.openai_api_key}
        if self.settings.openai_base_url:
            kwargs["base_url"] = self.settings.openai_base_url

        client = OpenAI(**kwargs)
        payload = compact_report_payload(report)

        response = client.responses.create(
            model=self.settings.openai_model,
            reasoning={"effort": "low"},
            max_output_tokens=260,
            text={"verbosity": "low"},
            instructions=(
                "너는 한국 부동산 입지·상권 분석가다. 제공된 근거만 사용한다. "
                "가격을 보장하지 말고, 투자 조언처럼 단정하지 않는다. "
                "한국어로 4문장 이내의 핵심 인사이트만 작성한다. "
                "형식: 1) 한줄 결론 2) 상승동력 3) 주의변수 4) 추가확인."
            ),
            input=json.dumps(payload, ensure_ascii=False),
        )
        return replace(report, llm_commentary=response.output_text.strip())


def compact_report_payload(report: AnalysisReport) -> dict[str, Any]:
    top_evidence = sorted(
        report.evidence,
        key=lambda item: (abs(item.impact) * item.reliability, item.reliability),
        reverse=True,
    )[:6]

    return {
        "target": report.address,
        "radius_km": report.radius_km,
        "score": report.score,
        "price_outlook": report.price_outlook,
        "confidence": report.confidence,
        "summary": report.summary,
        "location": report.location.__dict__ if report.location else None,
        "signals": {
            "good_news": [signal.__dict__ for signal in report.good_news[:1]],
            "bad_news": [signal.__dict__ for signal in report.bad_news[:1]],
            "policy_signals": [signal.__dict__ for signal in report.policy_signals[:1]],
            "local_factors": [signal.__dict__ for signal in report.local_factors[:1]],
        },
        "evidence": [
            {
                "title": item.title[:90],
                "summary": item.summary[:120],
                "source": item.source,
                "category": item.category,
                "sentiment": item.sentiment,
                "impact": item.impact,
                "reliability": item.reliability,
                "distance_km": item.distance_km,
                "tags": item.tags[:4],
            }
            for item in top_evidence
        ],
        "limitations": report.limitations,
    }
