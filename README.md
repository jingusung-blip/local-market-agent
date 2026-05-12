# 주변 상권/정책 영향 분석 에이전트

주소나 아파트 단지명을 입력하면 반경 2~5km 기준으로 주변 호재, 악재, 정책, 생활 인프라 신호를 모아 향후 가격에 줄 수 있는 영향을 분석하는 MVP입니다.

## 현재 구현된 흐름

1. 주소를 카카오 로컬 API로 좌표화합니다.
2. 카카오 로컬 API로 반경 내 지하철역, 학교, 병원, 대형마트, 문화시설 등 생활 인프라를 집계합니다.
3. 네이버 검색 API로 주소/단지명 기반 뉴스, 정책, 악재 키워드를 수집합니다.
4. 수집된 근거를 긍정/부정/정책/생활 인프라로 분류하고 0~100점 전망 점수를 냅니다.
5. `OPENAI_API_KEY`가 있으면 OpenAI Responses API로 분석 코멘트를 추가합니다.

뉴스/정책 검색은 키워드 기반입니다. 카카오 시설 수집은 좌표와 반경을 사용하지만, 네이버 뉴스/웹 검색 결과 자체는 엄밀한 거리 필터가 아닙니다. 리포트의 `limitations`에 이 차이를 명시합니다.

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
4. 배포가 끝나면 Render가 제공하는 `https://...onrender.com` URL로 접속합니다.

로컬의 `.env`는 `.gitignore`에 포함되어 있으므로 원격 저장소에 올리지 않습니다.

## 주요 파일

- `market_agent/agent.py`: 전체 파이프라인 조립
- `market_agent/geo.py`: 카카오 주소/시설 API 클라이언트
- `market_agent/collectors/naver.py`: 네이버 뉴스/웹 검색 수집기
- `market_agent/analysis/rule_engine.py`: 규칙 기반 점수화와 리포트 생성
- `market_agent/analysis/openai_analyzer.py`: OpenAI 분석 코멘트 추가
- `market_agent/server.py`: FastAPI 웹 UI
- `market_agent/cli.py`: 명령행 실행

## 데이터 출처 메모

- 카카오 로컬 API: https://developers.kakao.com/docs/latest/ko/local/dev-guide
- 네이버 검색 API 뉴스: https://developers.naver.com/docs/serviceapi/search/news/news.md
- OpenAI Responses API: https://developers.openai.com/api/docs/guides/text

## 주의

이 프로젝트는 투자 조언이나 가격 보장을 제공하지 않습니다. 실제 의사결정에는 실거래가, 전월세 추이, 공급 물량, 금리, 학군, 정비사업 단계, 규제 지역 여부, 현장 임장 데이터를 함께 검토해야 합니다.
