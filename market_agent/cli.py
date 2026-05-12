from __future__ import annotations

import argparse
import json

from market_agent.agent import LocalMarketAgent
from market_agent.models import AnalysisRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="주소/단지명 기반 주변 상권·정책 영향 분석")
    parser.add_argument("target", nargs="?", default="", help="분석할 주소 또는 아파트 단지명")
    parser.add_argument("--radius", type=float, default=3.0, help="분석 반경, 2~5km")
    parser.add_argument("--apartment-name", help="아파트 단지명")
    parser.add_argument("--offline", action="store_true", help="API 키 없이 데모 데이터로 실행")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    args = parser.parse_args()

    report = LocalMarketAgent().analyze(
        AnalysisRequest(
            address=args.target,
            radius_km=args.radius,
            apartment_name=args.apartment_name,
            offline=args.offline,
        )
    )

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"[{report.price_outlook}] {report.score}점")
    print(report.summary)
    if report.llm_commentary:
        print("\nAI 핵심 인사이트")
        print(report.llm_commentary)
    if report.limitations:
        print("\n분석 유의사항")
        for limitation in report.limitations:
            print(f"- {limitation}")


if __name__ == "__main__":
    main()
