# Local Market Agent 작업 기록

마지막 정리일: 2026-07-07

## 다음 세션에서 이어서 할 일 (2026-07-07 기준, 여기서부터 이어가면 됨)

**완료된 것**

- 부정어 처리, 정비사업 단계 가중치, 지역명 오탐 필터, MOLIT 실거래가 연동 코드 작업 완료.
- `.env`에 `MOLIT_API_KEY` 추가함. data.go.kr 활용신청 화면 스크린샷으로 승인 상태("처리상태: 승인", 활용기간 2026-03-19~2028-03-19)와 "일반 인증키" 값이 이 키와 정확히 일치하는 것을 확인함 — 키 자체는 문제없음.
- **엔드포인트 버그 수정함.** 처음 작성할 때 `RTMSDataSvcAptTradeDev`(레거시/개발용 이름)로 잘못 넣었었는데, 스크린샷의 End Point가 `RTMSDataSvcAptTrade`(Dev 없음)인 것을 보고 `market_agent/collectors/molit.py`의 `base_url`을 `https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade`로 수정함.
- **resultCode 버그 수정함.** 로컬에서 실제 키로 테스트했더니 `MolitApiError: MOLIT API error 000: OK` 에러가 났음 — 이 API는 성공 코드를 다른 data.go.kr API처럼 `"00"`이 아니라 `"000"`(0이 3개)으로 응답하는데, 코드에서 `!= "00"`만 체크해서 성공인데도 에러로 잘못 처리하던 버그였음. `set(result_code) != {"0"}` (0으로만 이루어졌는지 체크)로 수정. 회귀 테스트 2개 추가 (`test_parse_trade_items_accepts_triple_zero_result_code`, `test_parse_trade_items_raises_on_real_error_code`).
- 테스트 38개 모두 통과 확인 (샌드박스 내 격리 환경에서).
- **로컬 실제 호출 테스트 성공 (사용자 확인).** `MolitClient.fetch_trades('11680', '202506')`으로 강남구 실거래 리스트가 정상적으로 반환됨. MOLIT 실거래가 연동이 실제로 작동합니다.

**아직 안 끝난 것 — 순서대로**

1. **git 커밋 & 푸시.** 코드 변경분은 실제 폴더에 이미 반영되어 있지만 아직 커밋되지 않았습니다 (샌드박스에 GitHub 인증정보가 없어 직접 push 못함). 로컬 터미널에서:

   ```powershell
   cd "C:\Users\OK\Desktop\주변상권분석"
   git add -A
   git commit -m "Improve scoring accuracy: negation handling, redevelopment stages, region-aware news filtering, MOLIT real transaction data"
   git push origin main
   ```

2. **Render 환경변수 추가.** 푸시하면 자동 배포되는데, 배포된 서버에서도 실거래가 기능을 쓰려면 Render Dashboard → Environment Variables에 `MOLIT_API_KEY`를 로컬 `.env`와 동일한 값으로 추가해야 합니다 (로컬 `.env`는 자동으로 Render에 올라가지 않음).

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
- `상승동력`, `생활권`, `정책변수`, `주의신호` 4개 인사이트 제공, `MOLIT_API_KEY` 등록 시 `실거래가` 인사이트 추가
- 각 인사이트를 클릭하면 영향도, 신뢰도, 상세 해석, 근거 링크가 펼쳐짐
- OK저축은행 홈페이지 느낌을 참고한 주황/화이트 계열 UI
- Render 배포용 `render.yaml` 포함

### 2026-07-07 정확성/효율성 개선 (부동산 전문가 리뷰 반영)

- 감성 분류에 부정어 처리 추가: "침수 우려 해소", "규제 완화" 처럼 위험 키워드 주변에 완화 표현이 있으면 악재로 잘못 집계하지 않음
- 키워드 매칭 개수에 따라 영향도가 커지도록 조정 (기존에는 키워드 1개든 5개든 영향도가 고정값이었음)
- 정비사업(재건축/재개발) 진행 단계별 가중치 도입: 조합설립(0.7배) < 사업시행인가(0.85배) < 관리처분인가(1.0배) < 착공(1.2배) < 준공(1.3배). 기존에는 초기 추진 단계와 착공 단계를 동일하게 취급해 불확실성이 큰 사업도 점수에 동등하게 반영되는 문제가 있었음
- 네이버 뉴스/웹 검색 쿼리에 좌표 기반 구/동 이름을 자동으로 넣고, 결과 본문에 그 지역명이 없으면 신뢰도·영향도를 60%로 할인 + `지역확인필요` 태그 부여. 동명이인 단지(예: 다른 도시의 "자이", "래미안") 오탐 완화 목적. 단, 완전히 걸러내지는 않고 "확인이 더 필요한 신호"로 남겨둠 (거짓으로 버리는 것보다 낫다고 판단)
- 국토교통부 아파트매매 실거래자료 API(`MOLIT_API_KEY`) 연동 추가: 최근 3개월 vs 직전 3개월 평균 실거래가(만원/평)를 비교해 `market_data` 카테고리 근거를 생성. 키워드 추정치가 아닌 실제 거래 데이터라 점수 반영 시 가중치를 가장 높게 줌
- 카카오 주소 검색 결과에서 법정동코드(`b_code`)를 저장해 MOLIT API에 필요한 5자리 시군구 코드(LAWD_CD)를 별도 코드표 없이 바로 추출

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
MOLIT_API_KEY=
```

`MOLIT_API_KEY`는 data.go.kr에서 "국토교통부_아파트매매 실거래자료" 활용신청 후 발급되는 서비스키입니다. 키가 없으면 실거래가 근거 없이 기존 방식(뉴스/정책/생활 인프라)으로만 점수를 계산하고, 리포트에 "국토부 실거래가 API 키가 없어 실제 거래가 데이터는 반영되지 않았습니다" 안내가 붙습니다.

Render에서는 Dashboard의 Environment Variables에 같은 이름으로 등록합니다.

## AI 요약이 안 나오는 경우

2026-05-13에 확인한 내용:

- 로컬 `.env`에는 `OPENAI_API_KEY`가 설정되어 있었고, 모델은 `gpt-5.4-mini`였습니다.
- 실제 API 모드로 분석했을 때 AI 요약이 생성되지 않은 원인은 OpenAI 사용량 제한이었습니다.
- 이 경우 화면에는 긴 기술 에러 대신 아래와 같은 안내가 `분석 유의사항`에 표시됩니다.

```text
AI 요약은 OpenAI 사용량 제한으로 잠시 생성하지 못했습니다. 기본 입지 분석은 정상 처리되었고, 몇 초 뒤 다시 분석하면 요약이 붙을 수 있습니다.
```

AI 요약이 안 보일 때 체크할 순서:

1. 화면의 `데모` 체크가 꺼져 있는지 확인합니다. 데모 모드에서는 AI 요약을 실행하지 않습니다.
2. Render 배포 환경에서는 Dashboard의 Environment Variables에 `OPENAI_API_KEY`가 직접 등록되어 있는지 확인합니다.
3. OpenAI 사용량 제한 또는 결제/한도 문제를 확인합니다.
4. 짧은 시간에 여러 번 분석했다면 잠시 기다렸다가 다시 실행합니다.

다음 개선 후보:

- OpenAI 429 사용량 제한이 발생하면 1~2회 자동 재시도
- AI 요약 영역을 항상 보여주고, 실패 시 사유를 별도 상태로 표시
- Render 환경변수 누락 시 관리자용 점검 메시지 추가
- 토큰 사용량을 더 줄이기 위해 AI 요약 입력 근거를 추가 압축

## 주요 파일

- `market_agent/server.py`: FastAPI 웹 서버와 폼 처리
- `market_agent/agent.py`: 전체 분석 흐름 조합 (MOLIT 수집기 연동 포함)
- `market_agent/geo.py`: 카카오 주소/키워드 위치 검색, 법정동코드(b_code) 확보
- `market_agent/keywords.py`: 감성 분류, 부정어(완화 표현) 처리, 정비사업 단계별 가중치
- `market_agent/collectors/kakao_places.py`: 주변 생활 인프라 수집
- `market_agent/collectors/naver.py`: 네이버 뉴스/정책 수집, 최신 뉴스 필터, 지역명 기반 오탐 필터
- `market_agent/collectors/molit.py`: 국토부 아파트매매 실거래가 수집·집계
- `market_agent/analysis/rule_engine.py`: 점수, 전망, 인사이트 신호 계산 (market_data 카테고리 포함)
- `market_agent/analysis/openai_analyzer.py`: OpenAI 전문가 요약 생성
- `market_agent/templates/index.html`: 화면 구조 (실거래가 인사이트 카드 포함)
- `market_agent/static/styles.css`: 화면 디자인
- `render.yaml`: Render 배포 설정
- `tests/`: 자동 테스트 (test_keywords.py, test_molit.py 추가)

## 최근 반영된 커밋

- 2026-07-07: 감성분석 부정어 처리, 정비사업 단계 가중치, 지역명 기반 동명이인 필터, 국토부 실거래가 API 연동
- `d69e05e`: 인사이트 화면 단순화, 단지명만 입력해도 분석 가능
- `1dcc7d3`: OpenAI 429 원문 에러 숨김
- `abc311d`: 클릭 가능한 상세 인사이트 추가
- `4b9b3c0`: 최신 네이버 뉴스 우선 반영
- `6c46ea8`: 투자 검토용 보수 점수 기준 적용

## 다음에 바꾸기 좋은 후보

- 국토부 실거래가 데이터에 전월세(전세가율) 자료 추가해 갭투자 리스크 신호 반영
- 뉴스 기간을 2년에서 6개월 또는 1년으로 더 엄격하게 조정
- AI 요약 실패 시 자동 재시도와 눈에 띄는 상태 표시 추가
- 인사이트 상세에 실제 근거 기사 제목 목록 추가
- 카카오 생활 인프라를 병원, 학교, 지하철, 대형마트 등으로 더 세분화
- Render 유료 인스턴스로 전환해 첫 접속 지연 제거
- 지도 표시 또는 반경 원 시각화 추가
- 분석 결과 PDF 저장 기능 추가
- 단지명 검색 결과가 여러 개일 때 후보 선택 화면 추가
- 감성 분류를 키워드 매칭 대신 LLM 기반으로 교체 (문맥 이해도 향상, 단 비용/지연 증가 트레이드오프 있음)

## 주의사항

- `.env`와 API 키는 절대 GitHub에 올리지 않습니다.
- 분석 결과는 공개 검색 결과 기반이라 실제 투자 판단 전에는 실거래가, 매물, 수급, 정비계획 고시를 별도로 확인해야 합니다.
- `MOLIT_API_KEY`를 등록해도 실거래가는 동/단지 표본 기준이라 거래량이 적은 시기에는 변동폭이 과장될 수 있습니다 (표본 3건 미만이면 추세 대신 평균가만 표시).
- OpenAI API는 토큰 사용량 제한이 있으므로 짧은 시간에 여러 번 분석하면 요약 생성이 잠시 실패할 수 있습니다.
