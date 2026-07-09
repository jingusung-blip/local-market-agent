# Local Market Agent 작업 기록

마지막 정리일: 2026-07-09

## 다음 세션에서 이어서 할 일 (2026-07-09 기준, 여기서부터 이어가면 됨)

**2026-07-09 (5차): 구/동 단위 상승동력 스크리닝 신규 기능 (`/screen`) — ROADMAP 외 신규 요청**

- 사용자 질문 계기: "혹시 어떤 아파트 물건지가 상승동력이 있는지 이런 예측도 보여지게 만들 수 있나?" — 기존 에이전트는 주소 1개를 입력해야만 그 주변을 알려주는 조회형 구조라, "입력 없이 후보 지역을 먼저 찾아주는" 반대 방향 기능을 요청함.
- 아파트 단지 단위 스크리닝(전국 단지 마스터 데이터 필요, 큰 작업)과 구/동 단위 스크리닝(기존 MOLIT 시군구 벌크 조회 재사용 가능, 작은 작업) 중 사용자가 **구/동 단위**를 선택. 기존 주소 조회 기능(`/`)은 완전히 그대로 두고, 완전히 새로운 `/screen` 페이지를 추가하는 방식으로 진행 (사용자가 "폐기되냐 같이 가냐" 확인 후 "같이 간다"로 확정).
- 코드:
  - `market_agent/screener.py` (신규): 서울 25개 자치구(`SEOUL_DISTRICTS`, LAWD_CD 하드코딩) 대상으로 최근 3개월 vs 직전 3개월 실거래 중위가를 비교해 `pct_change`(%) 계산. 기존 `molit.py`의 `recent_year_months`/`price_per_area`, `molit_rent.py`의 `is_jeonse`/`deposit_per_area`, `regulation_areas.py`의 `is_regulated_area`를 그대로 재사용 — 새 API 연동 없이 기존 수집기 조합만으로 구현. 표본 5건 미만인 구는 `sufficient_sample=False`로 순위 밖(맨 뒤)으로 뺌 (추측성 순위 방지). `screen_districts()`가 `pct_change` 내림차순으로 정렬.
  - `market_agent/server.py`: `/screen` GET 라우트 추가. `MOLIT_API_KEY` 없으면 안내 문구만 표시. 25개 구 x 최대 6개월 조회라 매 요청마다 돌리면 느리고 API 호출량도 커서, ECOS 기준금리와 같은 방식으로 하루 단위 프로세스 내 캐싱(`_screen_cache`) 적용. `?refresh=1`로 강제 새로고침 가능.
  - `market_agent/templates/screen.html` (신규): 순위표(순위/자치구/실거래 변동률/전세가율/규제지역/표본) + "이 순위를 읽는 법" 주의사항 섹션 (후행지표라는 점, 구 평균이 단지별 편차를 가릴 수 있다는 점, 표본 부족/전세가율/규제목록 최신성/캐시 안내 5가지).
  - `market_agent/templates/index.html`: 상단 네비게이션에 "지역 스크리닝" 링크 추가.
  - `market_agent/static/styles.css`: `.nav-link`, `.screen-hero`, `.screen-facts`, `.refresh-link`, `.screen-table` 등 스타일 추가.
  - `tests/test_screener.py` (신규, 5개): `compute_district_momentum`(표본 부족/충분 판정, pct_change/전세가율 계산, rent_client 없을 때 스킵) + `screen_districts`(정렬 순서, 기본 서울 25개 구 사용) 검증.
- **테스트 작성 중 실수 → 디버깅**: 처음에 fake 거래 데이터의 month 키를 잘못 잡아서(최근/직전 윈도우 구분을 착각) 3개 테스트가 실패했음. `recent_year_months(date(2026,5,1), 3, offset=0/3)`을 직접 호출해 실제 산출값(recent=`202605,202604,202603` / baseline=`202602,202601,202512`)을 확인한 뒤 fake 데이터를 그 값에 맞게 수정해 해결. **추가로 이번에도 바로 그 mount-staleness 버그**가 발생 — Edit/Write로 파일을 고쳤는데도 `import`가 여전히 이전 버전을 읽는 현상 (`hasattr` 체크로 확인됨). `cat > 파일 << 'EOF'` 방식으로 강제로 다시 써서 해결. 전체 테스트 77개 통과 확인.
- 이 기능은 원래 `ROADMAP.md` 5개 항목에 없던, 세션 중 사용자 요청으로 새로 추가된 기능임 (5순위 청약 경쟁률과는 별개).
- **git 커밋 & 푸시 완료.** 커밋 `af73fa0` (9개 파일 변경), `origin/main`에 반영됨. Render 자동 배포됨 (새 API 키 불필요, 기존 `MOLIT_API_KEY` 재사용).

**2026-07-09 (4차): ECOS 실제 키 검증 완료**

- 사용자가 이미 발급받아둔 ECOS 인증키(비영리, 2026.03.19~2028.03.19, 상태 정상)를 `.env`에 추가. `verify_ecos_api.py`로 실제 호출 → 100개 지표 정상 수신, "한국은행 기준금리" 항목도 정확히 찾음 (현재 2.5%, 기준 20260707). 필드명(`CLASS_NAME`, `KEYSTAT_NAME`, `DATA_VALUE`, `CYCLE`, `UNIT_NAME`)이 코드와 정확히 일치해서 수정 없이 바로 동작 확인.
- 검증용 스크립트(`verify_ecos_api.py`)는 커밋 전 삭제 필요.
- Render 환경변수에 `ECOS_API_KEY` 추가 필요 (아직 미등록).

**2026-07-09 (3차): 한국은행 기준금리 연동 완료 (ROADMAP 4순위) + 표시 중복 버그 수정**

- ECOS "100대 통계지표(KeyStatisticList)" API 사용 — 통계표코드/항목코드를 몰라도 되는 사전 정의 지표 목록에서 "한국은행 기준금리"를 이름으로 바로 찾는 방식이라 매매 API 때 같은 코드 추측 버그 리스크가 없음. sample 엔드포인트(`https://ecos.bok.or.kr/api/KeyStatisticList/sample/json/kr/1/10`)로 실제 응답 스키마(`KeyStatisticList.row[].{CLASS_NAME,KEYSTAT_NAME,DATA_VALUE,CYCLE,UNIT_NAME}`)와 에러 형식(`{"RESULT":{"CODE","MESSAGE"}}`)을 인증키 없이 미리 확인함.
- 코드:
  - `market_agent/collectors/ecos.py` (신규): `EcosClient`, `parse_key_statistic_response`, `find_base_rate`, `build_base_rate_evidence`, `BaseRateCollector` (전국 공통 값이라 프로세스 단위로 하루 1회만 조회하도록 클래스 레벨 캐싱).
  - `market_agent/config.py`: `ECOS_API_KEY`/`ecos_enabled` 추가.
  - `market_agent/agent.py`: `BaseRateCollector`를 `ecos_enabled` 게이트로 추가, 실패 시 조용히 건너뜀.
  - `market_agent/models.py`: `AnalysisReport.base_rate_note` 필드 추가 (기준금리는 impact=0으로 넣어서 점수에 영향 없게 하되, 다른 신호에 묻혀 안 보이지 않도록 항상 노출되는 전용 필드로 분리).
  - `market_agent/analysis/rule_engine.py`: evidence에서 tags에 "기준금리"가 있는 항목을 찾아 `base_rate_note`로 뽑음.
  - `market_agent/templates/index.html`, `static/styles.css`: `report.base_rate_note`를 핵심 결론 아래 작은 안내문으로 표시.
  - `.env.example`, `README.md`: `ECOS_API_KEY` 문서화.
- **표시 중복 버그 수정 (2026-07-08에 진단만 하고 미뤄뒀던 것).** `category="policy"`이면서 `sentiment="negative"`인 근거(예: 규제지역 지정)가 정책변수 카드와 주의신호 카드에 동시에 뜨는 구조적 버그가 있었음. 이번에 규제지역 기능을 붙이면서 거의 모든 서울 주소 조회에서 이 버그가 재현될 게 뻔해서 지금 고침 — `rule_engine.build_report()`의 `good_news`/`bad_news` 필터에서 `amenity`/`policy`/`market_data` 카테고리를 제외해 카드별로 배타적으로 나오게 함. 회귀 테스트 추가.
- 테스트 9개(ecos) + 3개(rule_engine: 중복 버그, 기준금리 표시 2개) 추가, 전체 72개 통과.
- 아직 커밋/푸시 전.

**2026-07-09 (2차): 규제지역 지정 현황 반영 완료, 미분양 통계는 보류**

- `ROADMAP.md` 2순위(공식 미분양 통계)를 먼저 조사했으나, 실제로는 전국 통일 API가 없다는 걸 확인함. 원래 로드맵에 적어뒀던 "한국부동산원_부동산통계 조회 서비스(15134761)"는 2022년 API 개편 공지를 보니 미분양을 다루지 않고(주간아파트동향/주택가격동향/실거래가격지수 등 8종뿐), data.go.kr에서 "미분양" 검색 결과 국토부 차원 통합 API는 없고 **시/도별로 파편화**되어 있음 (경기도·부산광역시·경상남도 등 일부 지자체만 자체 API 보유, 서울은 API 자체가 없음). 국토부 통계누리 전국 통합 "미분양주택현황보고"도 API가 아니라 다운로드 형태. → 사용자와 상의 후 **보류**하고 3순위로 이동.
- **3순위(규제지역 지정 현황) 구현 완료.**
  - `market_agent/regulation_areas.py` (신규): 조정대상지역/투기과열지구 수동 유지보수 목록. 공식 API가 없어(ROADMAP에 이미 명시돼 있던 문제) 뉴스 발표를 근거로 사람이 갱신. WebSearch로 확인한 현재(2026-07-09) 지정 현황: 서울 25개 자치구 전역 + 경기 15곳(과천·광명·성남 분당/수정/중원·수원 영통/장안/팔달·안양 동안·용인 수지·의왕·하남 — 2025-10-15 지정, + 화성 동탄구·용인 기흥구·구리시 — 2026-07-01 추가). 출처: 대한민국 정책브리핑(2025-10-15 공식 발표) + 부동산케이스노트 블로그(2026-07-01 갱신, 1차 출처 아님, 실사용 전 국토부 고시 재확인 권장 문구를 evidence summary에 항상 포함).
  - `market_agent/collectors/regulation.py` (신규): `RegulationAreaCollector`, 좌표만 있으면 항상 실행(외부 API 호출 없음, 별도 키 불필요), category="policy"라 기존 rule_engine 정책 카테고리 로직을 그대로 재사용 (추가 변경 불필요).
  - `market_agent/agent.py`: `RegulationAreaCollector`를 `_collect()`에 추가.
  - `tests/test_regulation_areas.py` (신규, 8개). 전체 테스트 60개 통과.
- 아직 커밋/푸시 전. 아래 "아직 안 끝난 것" 참고.

**2026-07-09 (1차): 전월세 실거래가(전세가율) 구현 + 실제 키 검증 완료**

- `ROADMAP.md` 1순위 작업. data.go.kr "국토교통부_아파트 전월세 실거래가 자료" 활용신청 승인 완료 (자동승인, 활용기간 2026-07-09~2028-07-09). End Point가 `https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent`로 코드에 미리 넣어둔 값과 정확히 일치했고, 인증키도 기존 `MOLIT_API_KEY`를 그대로 재사용 (계정 단위 키라 매매/전월세 공용).
- 코드:
  - `market_agent/collectors/data_go_kr.py` (신규): XML 파싱 + resultCode 성공 판정을 매매/전월세 공통 함수로 분리 (`parse_xml_items`, `DataGoKrApiError`). `market_agent/collectors/molit.py`의 `MolitApiError`/`parse_trade_items`는 이제 이 공통 모듈을 감싸는 얇은 래퍼.
  - `market_agent/collectors/molit_rent.py` (신규): `RentClient`, `is_jeonse`/`deposit_per_area`, `build_jeonse_evidence`(전세가율 70%↑ positive, 50%↓ negative), `JeonseRatioCollector`.
  - `market_agent/agent.py`: `JeonseRatioCollector`를 `molit_enabled` 게이트 안에 추가, 실패 시 조용히 건너뜀 (경고 카드 없음).
  - `market_agent/templates/index.html`: 실거래가 인사이트 카드가 `market_signals` 전체를 순회하도록 변경 (매매/전세가율 각각 표시).
  - `tests/test_molit_rent.py` (신규, 12개). 전체 테스트 52개 통과.
- **실제 키 검증 완료.** 사용자가 `verify_rent_api.py`로 원본 XML 응답 확인 → 필드명(`deposit`, `monthlyRent`, `excluUseAr`, `aptNm`, `umdNm`) 전부 코드와 일치, resultCode도 매매와 동일하게 `000`. 매매 때와 달리 이번엔 버그 없이 한 번에 맞음. `verify_jeonse_ratio.py`로 `JeonseRatioCollector.collect()` 실제 통합 테스트도 성공 (강남구 대치동, 매매 표본 106건/전세 표본 56건, 전세가율 29.6% 산출 — 재건축 대상 단지 혼재로 낮게 나온 것으로 보이며, 특정 단지명을 지정하면 더 정확해짐. 매매 실거래가 기능과 동일한 특성).
- 검증용 임시 스크립트(`verify_rent_api.py`, `verify_jeonse_ratio.py`)는 커밋 전에 삭제 필요.
- 커밋 완료 여부는 아래 "아직 안 끝난 것" 참고.

**완료된 것**

- 부정어 처리, 정비사업 단계 가중치, 지역명 오탐 필터, MOLIT 실거래가 연동 코드 작업 완료.
- `.env`에 `MOLIT_API_KEY` 추가함. data.go.kr 활용신청 화면 스크린샷으로 승인 상태("처리상태: 승인", 활용기간 2026-03-19~2028-03-19)와 "일반 인증키" 값이 이 키와 정확히 일치하는 것을 확인함 — 키 자체는 문제없음.
- **엔드포인트 버그 수정함.** 처음 작성할 때 `RTMSDataSvcAptTradeDev`(레거시/개발용 이름)로 잘못 넣었었는데, 스크린샷의 End Point가 `RTMSDataSvcAptTrade`(Dev 없음)인 것을 보고 `market_agent/collectors/molit.py`의 `base_url`을 `https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade`로 수정함.
- **resultCode 버그 수정함.** 로컬에서 실제 키로 테스트했더니 `MolitApiError: MOLIT API error 000: OK` 에러가 났음 — 이 API는 성공 코드를 다른 data.go.kr API처럼 `"00"`이 아니라 `"000"`(0이 3개)으로 응답하는데, 코드에서 `!= "00"`만 체크해서 성공인데도 에러로 잘못 처리하던 버그였음. `set(result_code) != {"0"}` (0으로만 이루어졌는지 체크)로 수정. 회귀 테스트 2개 추가 (`test_parse_trade_items_accepts_triple_zero_result_code`, `test_parse_trade_items_raises_on_real_error_code`).
- 테스트 38개 모두 통과 확인 (샌드박스 내 격리 환경에서).
- **로컬 실제 호출 테스트 성공 (사용자 확인).** `MolitClient.fetch_trades('11680', '202506')`으로 강남구 실거래 리스트가 정상적으로 반환됨. MOLIT 실거래가 연동이 실제로 작동합니다.
- **git 커밋 & 푸시 완료.** 커밋 `dd7a109` (18개 파일 변경), `origin/main`에 반영됨. (중간에 `.git/index.lock` stale 파일 문제가 있었는데 `Remove-Item .git\index.lock`으로 해결함 — 다음에 또 이 에러 나면 같은 방법으로 지우면 됨.)
- Render 환경변수에 `MOLIT_API_KEY` 추가 진행 중 (Environment 탭 → Edit 버튼).

### 2026-07-08 실사용 중 발견된 버그: 메뉴/태그 목록을 문장으로 오인

사용자가 "고덕강일 대성베르힐"로 조회했더니 정책변수·주의신호 카드에 **똑같은 근거**("공고")가 중복으로 뜨고, 실제로는 미분양이 없는 단지인데 "미분양"으로 감점됨.

원인 두 가지:
1. **표시 중복**: 네이버 검색으로 가져온 기사 하나가 `category="policy"`이면서 동시에 `sentiment="negative"`로 판정되면, 정책변수(category 기준)와 주의신호(sentiment 기준) 두 카드에 같은 근거가 중복으로 나타남. 두 카드가 서로 다른 기준으로 필터링하기 때문에 생기는 구조적인 현상.
2. **진짜 원인**: 근거로 잡힌 텍스트가 실제 기사 본문이 아니라, 분양 블로그의 **메뉴/탭 목록**이었음 — `"고덕강일 대성베르힐: 고덕강일 대성베르힐 | 강동구 상일동 | 미분양 | 위치 | 입주자모집공고 | 분양가 | 평면 | 청약 | 모델하우스"`. "미분양"은 문장이 아니라 그 페이지에 있는 메뉴 탭 이름 중 하나였는데, 키워드 매칭기가 이걸 구분 못 하고 악재로 잘못 판정함.

**수정**: `market_agent/keywords.py`에 `is_tag_list_text()` 추가 — 텍스트에 파이프(`|`)가 3개 이상이면 메뉴/태그 목록으로 보고, `classify_sentiment`/`estimate_impact`에서 긍정·부정 키워드 기반 판정을 건너뜀 (정책 키워드로 카테고리 분류만 유지). 실사용에서 나온 실제 텍스트로 회귀 테스트 추가 (`test_menu_tag_list_does_not_trigger_false_negative_sentiment`). 테스트 총 40개 통과.

**커밋/푸시 완료.** `git show --stat HEAD`로 확인 결과 이 수정은 커밋 `dd7a109`(첫 대량 커밋)에 이미 포함되어 `origin/main`에 반영되어 있었음. 이후 커밋 `3781434`는 `ROADMAP.md` + 이 노트 파일 업데이트만 추가한 것. `git status` = clean, `origin/main`과 동기화 완료 확인함 (2026-07-08).

**원인 1(표시 중복)도 2026-07-09에 수정 완료.** 위 "2026-07-09 (3차)" 항목 참고 — `rule_engine.py`의 good_news/bad_news 필터에서 policy/amenity/market_data 카테고리를 제외하도록 고침.

**아직 안 끝난 것**

0. ~~구/동 단위 상승동력 스크리닝(`/screen`) git 커밋 & 푸시~~ **완료.** 커밋 `af73fa0` (9개 파일 변경), `origin/main`에 반영됨.

1. ~~전월세 실거래가 git 커밋 & 푸시~~ **완료.** 커밋 `a77ff61` (9개 파일 변경), `origin/main`에 반영됨.

2. ~~Render 환경변수 `MOLIT_API_KEY` 등록 확인~~ **완료.** Environment 탭 스크린샷으로 확인함 (2026-07-09). 매매 실거래가·전세가율 둘 다 배포 서버에서 정상 작동.

3. ~~규제지역 지정 현황 기능 git 커밋 & 푸시~~ **완료.** 커밋 `1ab90f3` (7개 파일 변경), `origin/main`에 반영됨. Render 자동 배포됨 (별도 환경변수 불필요, 외부 API 키 없이 동작).

4. ~~한국은행 기준금리 기능 git 커밋 & 푸시~~ **완료.** 커밋 `3940c6a` (13개 파일 변경), `origin/main`에 반영됨.

5. ~~ECOS 실제 키 검증 + git 커밋 & 푸시~~ **완료.** 커밋 `d2b81b3` (2개 파일), `origin/main`에 반영됨.

   (참고: `.env`는 `.gitignore`에 포함되어 실제 키 값은 커밋되지 않음 — 위 커밋은 `verify_ecos_api.py` 삭제와 노트 정리만 반영됨)

6. ~~Render 환경변수에 `ECOS_API_KEY` 추가~~ **완료** (2026-07-09, 사용자 확인).

**오늘(2026-07-09) 세션 요약**: 전월세 실거래가(전세가율), 규제지역 지정 현황, 한국은행 기준금리 3개 기능 전부 구현·검증·배포 완료. 정책/주의신호 표시 중복 버그도 수정. 4개 커밋(`a77ff61`, `1ab90f3`, `3940c6a`, `d2b81b3`) 전부 `origin/main`에 반영, Render 환경변수(`MOLIT_API_KEY`, `ECOS_API_KEY`) 등록도 확인 완료. 테스트 72개 통과.

7. **다음 로드맵: `ROADMAP.md` 5순위(청약 경쟁률).** 2순위(공식 미분양 통계)는 전국 통일 API가 없어 보류 상태 — 나중에 시/도별 파편화 API라도 부분 지원할지 다시 논의 필요. "이어서 하자"면 5순위(청약 경쟁률, 한국부동산원_청약홈)부터 시작하면 됨.

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
- `/screen` 페이지: 서울 25개 자치구를 최근 3개월 vs 직전 3개월 실거래 변동률 순으로 정렬한 스크리닝 (2026-07-09 신규, 주소 입력 없이 후보 지역을 먼저 훑어보는 용도)
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
- `market_agent/collectors/molit_rent.py`: 국토부 아파트 전월세 실거래가 수집, 전세가율 계산 (실제 키 검증 완료)
- `market_agent/collectors/data_go_kr.py`: data.go.kr XML 응답 공통 파서
- `market_agent/collectors/regulation.py`, `market_agent/regulation_areas.py`: 규제지역 수동 유지보수 목록/판정
- `market_agent/collectors/ecos.py`: 한국은행 기준금리 조회, 하루 단위 캐싱 (⚠️ 실제 키 검증 전)
- `market_agent/analysis/rule_engine.py`: 점수, 전망, 인사이트 신호 계산 (market_data 카테고리 포함, good_news/bad_news에서 policy/amenity/market_data 배타 처리)
- `market_agent/analysis/openai_analyzer.py`: OpenAI 전문가 요약 생성
- `market_agent/screener.py`: 구/동 단위 상승동력 스크리닝 (서울 25개 자치구 실거래 변동률 비교, 기존 수집기 재사용)
- `market_agent/templates/index.html`: 화면 구조 (실거래가/전세가율 인사이트 카드, market_signals 전체 순회, 기준금리 안내문, 지역 스크리닝 네비 링크)
- `market_agent/templates/screen.html`: 구/동 스크리닝 결과 화면
- `market_agent/static/styles.css`: 화면 디자인
- `render.yaml`: Render 배포 설정
- `tests/`: 자동 테스트 (test_keywords.py, test_molit.py, test_molit_rent.py, test_regulation_areas.py, test_ecos.py, test_screener.py 추가, 총 77개)

## 최근 반영된 커밋

- 2026-07-09: `af73fa0` 구/동 단위 상승동력 스크리닝(`/screen`) 추가
- 2026-07-09: `3940c6a` 한국은행 기준금리 연동 (ECOS API 키 검증 전) + 정책/주의신호 표시 중복 버그 수정
- 2026-07-09: `1ab90f3` 규제지역 지정 현황 수동 목록 + 수집기
- 2026-07-09: `a77ff61` 전월세 실거래가(전세가율) 수집기 + 실제 키 검증 완료
- 2026-07-08: `3781434` 메뉴/태그 목록 오탐 수정 (keywords.py는 이미 dd7a109에 포함되어 있었음) + ROADMAP.md 추가
- 2026-07-07: `dd7a109` 감성분석 부정어 처리, 정비사업 단계 가중치, 지역명 기반 동명이인 필터, 국토부 실거래가 API 연동
- `d69e05e`: 인사이트 화면 단순화, 단지명만 입력해도 분석 가능
- `1dcc7d3`: OpenAI 429 원문 에러 숨김
- `abc311d`: 클릭 가능한 상세 인사이트 추가
- `4b9b3c0`: 최신 네이버 뉴스 우선 반영
- `6c46ea8`: 투자 검토용 보수 점수 기준 적용

## 다음에 바꾸기 좋은 후보

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
