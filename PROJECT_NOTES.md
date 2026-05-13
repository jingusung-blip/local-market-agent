# Local Market Agent 작업 기록

마지막 정리일: 2026-05-13

## 프로젝트 목적

주소 또는 아파트 단지명을 입력하면 반경 2~5km 안의 생활 인프라, 뉴스, 정책, 위험 신호를 수집하고 향후 부동산 가격에 어떤 영향을 줄 수 있는지 요약하는 웹 에이전트입니다.

투자 수익을 보장하는 도구가 아니라, 공개 데이터와 API 검색 결과를 바탕으로 의사결정 전에 확인할 신호를 정리하는 분석 보조 도구입니다.

## 현재 주요 기능

- 주소 또는 아파트 단지명만 입력해도 분석 가능
- 카카오 API로 주소/단지명 위치 검색
- 카카오 장소 검색으로 반경 내 생활 인프라 수집
- 네이버 검색 API로 뉴스와 정책 자료 수집
- 네이버 뉴스는 최신 뉴스 중심으로 반영
  - 뉴스 발행일을 파싱
  - 최근 2년 이내 뉴스만 분석에 반영
  - 최신 기사일수록 신뢰도와 영향도 가중치 상승
  - 같은 주제 안에서는 최신 근거를 대표 설명으로 우선 사용
- OpenAI API가 있으면 전문가 요약 생성
- OpenAI 사용량 제한이 발생해도 긴 기술 에러 대신 짧은 안내문 표시
- 점수는 보수적인 투자 검토 기준으로 계산
  - 기본점을 50점보다 낮게 시작
  - 생활 인프라 플러스 점수에는 상한 적용
  - 악재와 데이터 부족은 더 크게 반영
  - 높은 점수는 뉴스, 정책, 생활권, 리스크 점검이 함께 잡힐 때만 가능
- `상승동력`, `생활권`, `정책변수`, `주의신호` 4개 인사이트 제공
- 각 인사이트를 클릭하면 영향도, 신뢰도, 상세 해석, 근거 링크가 펼쳐짐
- OK저축은행 홈페이지 느낌을 참고한 주황/화이트 계열 UI
- Render 배포용 `render.yaml` 포함

## 실행 방법

로컬 실행:

```powershell
.\.venv\Scripts\python.exe -m uvicorn market_agent.server:app --host 127.0.0.1 --port 8000
```

브라우저:

```text
http://127.0.0.1:8000
```

테스트:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 배포

GitHub 저장소:

```text
https://github.com/jingusung-blip/local-market-agent
```

Render는 GitHub `main` 브랜치와 연결되어 있으면 push 이후 자동 배포됩니다.

Render에서 접속 시 `Application loading`이 자주 보이는 이유:

- Render Free Web Service는 15분 동안 요청이 없으면 자동으로 잠듭니다.
- 다음 접속 때 다시 켜지면서 최대 약 1분 정도 로딩이 생길 수 있습니다.
- 유료 인스턴스로 변경하면 이 자동 절전이 사라집니다.

## 환경 변수

실제 키는 `.env`에만 저장하고 GitHub에는 올리지 않습니다.

필요한 값:

```text
KAKAO_REST_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.4-mini
```

Render에서는 Dashboard의 Environment Variables에 같은 이름으로 등록합니다.

## 주요 파일

- `market_agent/server.py`: FastAPI 웹 서버와 폼 처리
- `market_agent/agent.py`: 전체 분석 흐름 조합
- `market_agent/geo.py`: 카카오 주소/키워드 위치 검색
- `market_agent/collectors/kakao_places.py`: 주변 생활 인프라 수집
- `market_agent/collectors/naver.py`: 네이버 뉴스/정책 수집, 최신 뉴스 필터
- `market_agent/analysis/rule_engine.py`: 점수, 전망, 인사이트 신호 계산
- `market_agent/analysis/openai_analyzer.py`: OpenAI 전문가 요약 생성
- `market_agent/templates/index.html`: 화면 구조
- `market_agent/static/styles.css`: 화면 디자인
- `render.yaml`: Render 배포 설정
- `tests/`: 자동 테스트

## 최근 반영된 커밋

- `d69e05e`: 인사이트 화면 단순화, 단지명만 입력해도 분석 가능
- `1dcc7d3`: OpenAI 429 원문 에러 숨김
- `abc311d`: 클릭 가능한 상세 인사이트 추가
- `4b9b3c0`: 최신 네이버 뉴스 우선 반영

## 다음에 바꾸기 좋은 후보

- 뉴스 기간을 2년에서 6개월 또는 1년으로 더 엄격하게 조정
- 인사이트 상세에 실제 근거 기사 제목 목록 추가
- 카카오 생활 인프라를 병원, 학교, 지하철, 대형마트 등으로 더 세분화
- Render 유료 인스턴스로 전환해 첫 접속 지연 제거
- 지도 표시 또는 반경 원 시각화 추가
- 분석 결과 PDF 저장 기능 추가
- 단지명 검색 결과가 여러 개일 때 후보 선택 화면 추가

## 주의사항

- `.env`와 API 키는 절대 GitHub에 올리지 않습니다.
- 분석 결과는 공개 검색 결과 기반이라 실제 투자 판단 전에는 실거래가, 매물, 수급, 정비계획 고시를 별도로 확인해야 합니다.
- OpenAI API는 토큰 사용량 제한이 있으므로 짧은 시간에 여러 번 분석하면 요약 생성이 잠시 실패할 수 있습니다.
