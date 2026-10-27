# WO-23 Codex → Claude 전달 기록

## 상태

Ship Gate 전체를 실제 표본과 로컬 PostgreSQL로 확인했습니다. OpenDART API 인증키와 원본 파일은 프로젝트 로컬에만 있으며 전달물·Git에는 포함하지 않습니다.

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| XBRL 동일 문맥에서 분기·누적 숫자 팩트를 보존한다 | `src/xbrl.py`; `tests/test_xbrl.py`; 접수번호 `20230515001446` 원본 ZIP | 같은 기간·차원에 대응하지만 원천 문맥 ID가 다른 숫자 팩트를 보존. 영문·한글 텍스트 125건은 수치 fact로 적재하지 않음 | Codex가 실원본 충돌을 조사해 문맥 ID 보존·숫자만 적재를 구현, Codex 시험 | 확인됨 |
| 실제 분기 정정 숫자 차이를 SCD Type 2로 적재한다 | `results/experiment.json`; receipts `20230515001446`, `20230526000581` | 원본 544 facts, 정정본 542; 변경 6, 추가 0, 삭제 2, 유지 536 | 사용자가 API 키를 로컬 `.env`에 설정하고 실행을 지시, Codex 수집·구현 | 확인됨 |
| 날짜 기준 PIT가 두 원본 버전과 일치한다 | `results/experiment.json`; `src/db.py::query_pit` | 원본 시점 544/544 일치, 정정 시점 542/542 일치 | Codex 구현·측정 | 확인됨 |
| overwrite는 과거값을 재현하지 못한다 | `results/experiment.json`; `src/compare.py` | 정정 이후 최신값으로 과거 조회 시 원본 값 8개 불일치 | Codex 구현·측정 | 확인됨 |
| 행 수에 따른 조회 지연을 비교했다 | `results/benchmark.json`; PostgreSQL 16 Docker | 1k/10k/50k 행에서 중앙값 0.163/0.266/0.757ms, P95 0.283/0.365/1.049ms; 각 30회 | Codex 구현·실행 | 확인됨 (합성 행·로컬 연결 측정) |
| Python 3.11 로직을 회귀 검증했다 | `tests/`; 호스트 및 Docker 실행 | 8 passed | Codex 구현·시험 | 확인됨 |
| API 요청 상한을 지켰다 | pipeline 출력의 `request_attempts`, `request_cap` | 최종 표본 수집 7/300 요청. 후보 탐색 단계도 별도 실행별 상한 이내 | Codex 요청 장부 기록 | 확인됨 |

## 실제 판단 장면

### 1. 표본 선정은 정정 표시가 아니라 재무 숫자 변경을 기준으로 좁힘

- **SONG의 목표**: 실제 분기 정정 사례에서 PIT·overwrite 차이를 검증.
- **초기 시도**: 삼성전자·SK하이닉스·현대자동차 등 후보를 조회했으나, 분기 정정 후보는 숫자 재무 팩트 변경이 없었다. 처음 잡힌 변경 사례는 연간 보고서여서 분기 Ship Gate를 충족하지 못했다.
- **재검토**: OpenDART 전체 분기 공시 목록에서 정정 표식을 탐색하고 후보별 원본·정정 XBRL을 직접 비교.
- **관측과 선택**: 아이티센씨티에스 분기보고서 후보를 확인했다. 숫자 facts 6개 변경, 2개 제거를 확인해 최종 표본으로 고정했다.
- **결과**: 회사 이름이 알려졌다는 이유가 아니라 실제 수치 차이가 검증된 점을 선정 근거로 삼았다.

### 2. XBRL 중복 오류를 조사해 숫자와 문맥을 올바르게 분리

- **Codex 1차 처리**: 정규화한 기간·차원·단위·개념을 fact 키로 사용.
- **관측**: 실제 원본에서 AuthorName·감사의견처럼 영문·한글 문자열이 같은 문맥에 함께 있어 DB 고유키가 충돌했다. 이를 제외한 뒤에는 분기/누적 숫자값이 기간·차원 문자열만으로 충돌했다.
- **근거와 수정**: XBRL 원천 문맥 ID를 키에 보존하면 같은 기간과 차원으로 직렬화된 별도 보고 맥락을 구분한다. 비숫자 텍스트를 숫자 저장에서 제외하고, 동일 원천 문맥에서 서로 다른 숫자가 나오면 임의 선택 대신 오류를 발생시킨다.
- **결과**: 실제 분기 원본·정정본을 각각 544개와 542개 numeric facts로 파싱. 회귀 테스트가 비숫자 이중 언어 텍스트 제외와 context ID 차이 보존을 확인.

### 3. 접수일 정밀도 이상으로 PIT 순서를 만들어 내지 않음

- **Codex 구현**: `rcept_dt`를 날짜 범위로 모델링하고 같은 날 접수된 원본·정정 쌍은 날짜만으로 순서를 구분할 수 없어 후보에서 제외.
- **근거**: API 목록은 접수일을 제공하지만 이 구현이 쓰는 원천에는 일중 접수 시각이 없다. 인위적 시각을 넣으면 과거 시점 답변이 실제 공시보다 정밀해 보인다.
- **검증**: 같은 날 원본·정정 테스트가 후보에서 제외되는 것을 확인. 실제 선택된 표본은 서로 다른 날짜로 PIT 비교.
- **결과**: 실제 원천 정밀도에 맞는 PIT 간격을 제공하고, 일중 재현은 별도 데이터 요구로 남김.

## 구현 요약

- `src/opendart.py`: 요청 상한, 재시도, 자격증명 URL/예외 노출 회피.
- `src/revisions.py`: 분기·반기·3분기 보고서, 정정 표시, 날짜 구분 가능한 원본·정정 쌍 탐색.
- `src/xbrl.py`: 접수번호별 XBRL Zip, numeric facts, scale/sign, context ID 파싱; conflicting numeric duplicate 방지.
- `src/db.py`, `sql/001_schema.sql`: PostgreSQL SCD Type 2 daterange 적재, 변경·추가·삭제, PIT 쿼리.
- `src/compare.py`: revision delta, PIT와 overwrite 대조.
- `src/benchmark.py`, `results/benchmark.json`: 로컬 PostgreSQL의 합성 행 수 규모별 지연 측정.
- `results/experiment.json`: 실제 접수번호, fact counts, delta, PIT 원본 일치, overwrite 차이, 해시, API 시도 수.
- `data/`의 기업 코드 및 접수번호별 XBRL 원본, `.env`는 로컬 무시 파일이며 Git/Claude ZIP에서 제외.

## 실행·검증 기록

- Python 3.11 호스트 및 Docker 이미지에서 `pytest -q`: **8 passed**.
- Docker PostgreSQL 16에서 스키마 초기화와 synthetic revision check를 확인. 원본 2행 이후 정정에서 값 변경 1·삭제 1·추가 2가 반영되고 두 시점 PIT 결과가 분리됨.
- 후보 선별 실행에서 숫자 변경이 없는 분기 정정 사례를 확인하고, 더 넓은 분기 공시 후보를 살펴 최종 한 기업을 선택.
- 최종 OpenDART 적재는 7회 API 요청으로 완료. `MAX_API_REQUESTS=300` 안에서 실행됨.
- 최종 실제 표본과 수치는 `results/experiment.json`; synthetic DB 성능 결과는 `results/benchmark.json`에 보존.

## Claude 작업 범위

GitHub 프로젝트 요약과 Notion WO-23 케이스 스터디에 README의 확인된 결과를 반영. 공개 전 `CLAUDE.md`의 시간 표현 금지, 전문용어 첫 원어 병기, 용어집 규칙을 따르고, 성능은 로컬 PostgreSQL 합성 행 측정이라고 표시. API 인증키와 raw XBRL 원본은 공개 문서나 ZIP에 포함하지 말 것. 사용자 회고를 새로 만들어 SONG의 말로 인용하지 말 것.
