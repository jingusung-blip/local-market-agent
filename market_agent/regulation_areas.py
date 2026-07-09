"""규제지역(조정대상지역/투기과열지구) 수동 유지보수 목록.

⚠️ 국토교통부는 이 정보를 REST API로 제공하지 않습니다 (data.go.kr에 관련 공식
API 없음, molit.go.kr 고시 페이지도 JS 렌더링이라 자동 스크래핑에 적합하지 않음).
그래서 이 파일은 뉴스/정책 발표를 근거로 사람이 주기적으로 갱신하는 정적 목록입니다.
정부가 새로 지정/해제 발표를 할 때마다 이 파일도 함께 갱신해야 합니다.

법적 효력이 있는 최종 확인은 반드시 국토교통부 고시
(https://www.molit.go.kr/policy/stable/sta_b_03.jsp)를 기준으로 하세요. 이 목록은
"참고용 신호"이며, 실제 세금/대출/청약 판단의 근거로 그대로 사용하면 안 됩니다.

기준일: 2026-07-09

연혁:
- 2025-10-15 지정: 서울 25개 자치구 전역(기존 강남·서초·송파·용산 유지 + 나머지
  21개 자치구 신규) + 경기 12개 지역(과천, 광명, 성남 분당·수정·중원, 수원 영통·
  장안·팔달, 안양 동안, 용인 수지, 의왕, 하남)
- 2026-07-01 추가 지정: 화성시 동탄구, 용인시 기흥구, 구리시 (경기 규제지역 12→15곳)

출처:
- 대한민국 정책브리핑, "서울 전역·경기 12곳 투기과열지구·토지거래허가구역 지정"
  (2025-10-15) https://www.korea.kr/news/policyNewsView.do?newsId=148950973
- 부동산케이스노트, "조정대상지역 (2026년 최신)" (2026-07-01 갱신) —
  화성동탄·용인기흥·구리 추가 지정 반영. 1차 공식 출처가 아니므로 실사용 전
  국토부 고시로 재확인 권장.
  https://realscasenote.com/조정대상지역-2026년-기준/
"""
from __future__ import annotations


LAST_UPDATED = "2026-07-09"

# 서울은 25개 자치구 전역이 지정 상태 (2025-10-15 이후).
SEOUL_ALL_DISTRICTS_REGULATED = True

# 경기도 내 지정 지역. Kakao 지오코딩 응답의 region_2depth 형식
# ("성남시 분당구", "수원시 영통구"처럼 시+구가 공백으로 이어진 문자열, 또는
# 과천시/광명시처럼 시 단독)에 맞춰 정리했습니다.
GYEONGGI_REGULATED_AREAS: set[str] = {
    "과천시",
    "광명시",
    "성남시 분당구",
    "성남시 수정구",
    "성남시 중원구",
    "수원시 영통구",
    "수원시 장안구",
    "수원시 팔달구",
    "안양시 동안구",
    "용인시 수지구",
    "의왕시",
    "하남시",
    "화성시 동탄구",
    "용인시 기흥구",
    "구리시",
}


def _normalize(text: str | None) -> str:
    return (text or "").replace(" ", "")


def is_regulated_area(region_1depth: str | None, region_2depth: str | None) -> bool:
    """region_1depth: 시/도 (예: '서울특별시'), region_2depth: 시/군/구
    (예: '강남구', '성남시 분당구'). 둘 다 Kakao 지오코딩 결과에서 옵니다."""
    if region_1depth and "서울" in region_1depth and SEOUL_ALL_DISTRICTS_REGULATED:
        return True

    if not region_2depth:
        return False

    norm_target = _normalize(region_2depth)
    for area in GYEONGGI_REGULATED_AREAS:
        norm_area = _normalize(area)
        if norm_area in norm_target or norm_target in norm_area:
            return True
    return False
