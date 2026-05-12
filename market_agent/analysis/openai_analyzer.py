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
            max_output_tokens=700,
            text={"verbosity": "low"},
            instructions=(
                "You are a Korean real estate market analyst. "
                "Use only the supplied evidence. Do not guarantee prices. "
                "Return concise Korean commentary with four short sections: "
                "핵심 결론, 상승 요인, 하방 리스크, 추가 확인 필요 데이터."
            ),
            input=json.dumps(payload, ensure_ascii=False),
        )
        return replace(report, llm_commentary=response.output_text.strip())


def compact_report_payload(report: AnalysisReport) -> dict[str, Any]:
    top_evidence = sorted(
        report.evidence,
        key=lambda item: (abs(item.impact) * item.reliability, item.reliability),
        reverse=True,
    )[:12]

    return {
        "address": report.address,
        "radius_km": report.radius_km,
        "score": report.score,
        "price_outlook": report.price_outlook,
        "confidence": report.confidence,
        "summary": report.summary,
        "location": report.location.__dict__ if report.location else None,
        "signals": {
            "good_news": [signal.__dict__ for signal in report.good_news[:3]],
            "bad_news": [signal.__dict__ for signal in report.bad_news[:3]],
            "policy_signals": [signal.__dict__ for signal in report.policy_signals[:3]],
            "local_factors": [signal.__dict__ for signal in report.local_factors[:3]],
        },
        "evidence": [
            {
                "title": item.title[:140],
                "summary": item.summary[:220],
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
