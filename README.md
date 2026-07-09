# 주변 상권/정책 영향 분석 에이전트

주소나 아파트 단지명을 입력하면 반경 2~5km 기준으로 주변 호재, 악재, 정책, 생활 인프라 신호를 모아 향후 가격에 줄 수 있는 영향을 분석하는 MVP입니다.

## 현재 구현된 흐름

1. 주소를 카카오 로컬 API로 좌표화합니다 (법정동코드/구·동 정보도 함께 확보합니다).
2. 카카오 로컬 API로 반경 내 지하철역, 학교, 병원, 대형마트, 문화시설 등 생활 인프라를 집계합니다.
3. 네이버 검색 API로 주소/단지명 기반 뉴스, 정책, 악재 키워드를 수집합니다. 좌표에서 얻은 구/동 이름을 검색어에 함께 넣고, 결과 본문에 그 지역명이 없으면 신뢰도를 낮춰 동명이인 단지(예: 여러 도시의 "자이", "래미안") 오탐을 줄입니다.
4. `MOLIT_API_KEY`가 있으면 국토교통부 아파트매매 실거래 자료로 최근 3개월과 직전 3개월의 평균 실거래가를 비교해 실제 가격 추세 신호를 추가합니다.
5. 같은 키로 아파트 전월세 실거래 자료도 함께 조회해 전세가율(전세 중위가 ÷ 매매 중위가)을 계산합니다. 전월세 API는 매매 API와 별도로 data.go.kr 활용신청이 필요합니다 (2026-07-09 실제 키로 검증 완료). 미승인 계정이거나 API 호출이 실패하면 조용히 건너뛰고 매매 실거래가만 반영합니다.
6. 좌표의 시/군/구가 조정대상지역·투기과열지구로 지정되어 있는지 확인해 정책 근거로 추가합니다. 국토교통부가 이 정보를 API로 제공하지 않아 `market_agent/regulation_areas.py`에 뉴스 발표를 근거로 사람이 수동 갱신하는 정적 목록을 사용합니다 (기준일은 파일 상단에 표기). 외부 API 호출이 없어 별도 키 없이 항상 동작합니다.
7. `ECOS_API_KEY`가 있으면 한국은행 기준금리를 조회해 리포트에 거시 맥락 한 줄로 보여줍니다. 특정 단지와 무관한 전국 공통 값이라 점수 계산에는 반영하지 않고, 하루 한 번만 조회하도록 캐싱합니다.
8. 수집된 근거를 긍정/부정/정책/생활 인프라/실거래가로 분류하고, 정비사업 관련 근거는 진행 단계(조합설립~착공/준공)에 따라 가중치를 다르게 반영해 0~100점 전망 점수를 냅니다.
9. `OPENAI_API_KEY`가 있으면 OpenAI Responses API로 분석 코멘트를 추가합니다.

뉴스/정책 검색은 키워드 기반이며, 부정 키워드 주변에 "해소/완화/없음" 같은 표현이 있으면 리스크가 해소된 것으로 보정합니다. 카카오 시설 수집은 좌표와 반경을 사용하지만, 네이버 뉴스/웹 검색 결과 자체는 엄밀한 거리 필터가 아니라 지역명 매칭에 의존합니다. 리포트의 `limitations`에 이 차이를 명시합니다.

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

`.env`에 필요한 키를 넣습니다.

- `KAKAO_REST_API_KEY`: 주소 좌표화와 반경 내 시설 수집
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 뉴스/정책 수집
- `OPENAI_API_KEY`: 선택 사항, LLM 분석 코멘트
- `MOLIT_API_KEY`: 선택 사항이지만 강력 권장. 실제 실거래가 반영 (data.go.kr에서 "국토교통부_아파트매매 실거래자료"와 "국토교통부_아파트 전월세 실거래가 자료" 둘 다 활용신청 필요, 승인되면 같은 인증키를 그대로 사용)
- `ECOS_API_KEY`: 선택 사항. 한국은행 기준금리 맥락 정보 (ecos.bok.or.kr에서 회원가입 시 자동 발급)

## 실행

웹 UI:

```powershell
uvicorn market_agent.server:app --reload --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

CLI:

```powershell
python -m market_agent.cli "서울특별시 강남구 테헤란로 152" --radius 3
```

API 키 없이 구조만 확인:

```powershell
python -m market_agent.cli "서울특별시 강남구 테헤란로 152" --radius 3 --offline
```

## Render 배포

이 프로젝트는 Render Blueprint 배포용 `render.yaml`을 포함합니다.

1. 프로젝트를 GitHub/GitLab/Bitbucket 저장소에 push합니다.
2. Render Dashboard에서 새 Blueprint를 만들고 저장소를 연결합니다.
3. 환경변수에 아래 값을 입력합니다.
   - `KAKAO_REST_API_KEY`
   - `NAVER_CLIENT_ID`
   - `NAVER_CLIENT_SECRET`
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`: 기본값 `gpt-5.4-mini`
   - `MOLIT_API_KEY`: 선택 사항, 실거래가/전세가율 반영
   - `ECOS_API_KEY`: 선택 사항, 기준금리 맥락 정보
4. 배포가 끝나면 Render가 제공하는 `https://...onrender.com` URL로 접속합니다.

로컬의 `.env`는 `.gitignore`에 포함되어 있으므로 원격 저장소에 올리지 않습니다.

## 주요 파일

- `market_agent/agent.py`: 전체 파이프라인 조립
- `market_agent/geo.py`: 카카오 주소/시설 API 클라이언트
- `market_agent/keywords.py`: 감성 분류, 부정어 처리, 정비사업 단계 가중치
- `market_agent/collectors/naver.py`: 네이버 뉴스/웹 검색 수집기, 지역명 기반 오탐 필터
- `market_agent/collectors/molit.py`: 국토부 매매 실거래가 수집기 (최근 3개월 vs 직전 3개월 비교)
- `market_agent/collectors/molit_rent.py`: 국토부 전월세 실거래가 수집기, 전세가율 계산
- `market_agent/collectors/data_go_kr.py`: data.go.kr XML 응답 공통 파서 (resultCode 처리 공유)
- `market_agent/collectors/regulation.py`, `market_agent/regulation_areas.py`: 규제지역(조정대상지역·투기과열지구) 수동 유지보수 목록과 판정 로직
- `market_agent/collectors/ecos.py`: 한국은행 ECOS "100대 통계지표" API로 기준금리 조회, 하루 단위 캐싱
- `market_agent/analysis/rule_engine.py`: 규칙 기반 점수화와 리포트 생성
- `market_agent/analysis/openai_analyzer.py`: OpenAI 분석 코멘트 추가
- `market_agent/server.py`: FastAPI 웹 UI
- `market_agent/cli.py`: 명령행 실행

## 데이터 출처 메모

- 카카오 로컬 API: https://developers.kakao.com/docs/latest/ko/local/dev-guide
- 네이버 검색 API 뉴스: https://developers.naver.com/docs/serviceapi/search/news/news.md
- 국토교통부 아파트매매 실거래자료 (data.go.kr): https://www.data.go.kr/data/15058747/openapi.do
- 국토교통부 아파트 전월세 실거래가 자료 (data.go.kr): https://www.data.go.kr/data/15126474/openapi.do
- 한국은행 ECOS Open API: https://ecos.bok.or.kr/api/
- OpenAI Responses API: https://developers.openai.com/api/docs/guides/text

## 주의

이 프로젝트는 투자 조언이나 가격 보장을 제공하지 않습니다. `MOLIT_API_KEY`를 등록해도 실거래가 데이터는 반경이 아닌 동/단지 표본 기준이라 거래량이 적은 시기에는 변동폭이 커질 수 있습니다. 규제지역 지정 현황은 공식 API가 없어 `market_agent/regulation_areas.py`에 사람이 수동으로 갱신하는 목록이므로, 최신 지정/해제 여부는 반드시 국토교통부 고시로 재확인해야 합니다. 실제 의사결정에는 실거래가, 전월세 추이, 공급 물량, 금리, 학군, 정비사업 단계, 규제 지역 여부, 현장 임장 데이터를 함께 검토해야 합니다.
