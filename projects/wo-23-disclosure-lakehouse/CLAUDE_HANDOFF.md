# WO-23 Codex → Claude 전달 기록

## 상태

코드와 오프라인 단위 테스트는 준비됨. OpenDART API 키가 비어 있어 실제 공시 원본 수집, PostgreSQL 적재 Ship Gate, 실제 데이터 PIT·덮어쓰기 비교, 실행 성능 벤치마크는 보류 상태다. 결과를 추정하거나 합성 값으로 대체하지 않았다.

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| 날짜 형식 파서는 OpenDART 접수일 포맷에 맞아야 한다 | `tests/test_revisions.py`; 첫 실행 실패, 파서 수정 뒤 재실행 | `YYYYMMDD` 테스트 입력, 최종 테스트 7 passed | Codex 구현·시험, 테스트 실패를 근거로 수정 | 확인됨 |
| 같은 날 정정은 날짜 범위만으로 순서를 재현할 수 없다 | `src/revisions.py`, 동일 날짜 테스트 | 같은 날 원본·정정 쌍 0개 반환 | Codex가 원천 날짜 정밀도에 맞춰 설계 | 확인됨 |
| XBRL 원본 단위의 비교를 지원한다 | `src/xbrl.py`, `tests/test_xbrl.py` | Zip 내 XBRL XML의 개념·문맥·단위·숫자 추출과 scale 변환 테스트 통과 | Codex 구현·시험 | 확인됨 |
| 정정 후 과거 행과 최신 값 대조군이 달라질 수 있다 | `tests/test_compare.py` | 합성 팩트 100→120에서 PIT는 이전 100, overwrite는 최신 120 반환 | Codex 구현·시험 | 확인됨 (합성 로직에 한함) |
| 실제 기업 정정으로 PIT가 원본과 일치한다 | API 키 없음, `results/experiment.json` 미생성 | 실데이터 관측값 없음 | 사용자 작업지시서에 목표 명시, Codex 구현 대기 | 근거 없음 |
| 통제된 행 규모에 따른 PIT 쿼리 지연을 측정했다 | `results/benchmark.json`; PostgreSQL 16 로컬 실행 | 1k: 중앙값 0.163 ms, p95 0.283 ms; 10k: 0.266/0.365 ms; 50k: 0.757/1.049 ms | Codex 구현·실행 | 확인됨 (합성 데이터 측정) |

## 실제 판단 장면

### 1. 입력 날짜 테스트가 실패해 파서를 수정

- **SONG 요청/우선순위**: 실제 공시 접수일과 재무 정정을 기준으로 검증할 것.
- **Codex 1차 구현**: 날짜 문자열을 ISO 포맷으로 해석.
- **관측**: 테스트 입력 `20240510`에서 `filing_from_row`가 `None`을 반환해 정정 쌍을 만들지 못함.
- **수정**: OpenDART 응답에 맞춰 `%Y%m%d`로 파싱하고, 날짜 형식 테스트를 추가.
- **결과**: 테스트 전체 7개 통과. 실 API 응답 확인은 API 키가 없어 보류.

### 2. 접수일보다 세밀한 유효 시각을 만들지 않음

- **Codex 제안/구현**: 수신 원천의 접수일을 `daterange`로 저장하고 같은 날 정정은 선택 대상에서 제외.
- **근거**: `rcept_dt`는 날짜 단위이며 같은 날 두 접수의 시각 순서를 제공하지 않음. 이를 시각으로 바꾸면 가짜 정밀도가 생김.
- **검증**: `tests/test_revisions.py`에서 같은 날짜의 원본·정정은 구분 불가 후보로 반환하지 않는 것을 확인.
- **결과**: 날짜로 구분 가능한 사례만 PIT 대조 대상이 됨. 일중 시점 재현은 다음 단계.

### 3. 최신 재무 요약 API 대신 접수번호별 XBRL 원본을 기준으로 삼음

- **Codex 조사**: 공시 목록 API에서 정정·접수번호를 찾고, XBRL 원본파일 API의 접수번호 인자로 버전별 파일을 가져오는 흐름을 구현.
- **선택 근거**: 작업 질문은 정정 이전 원본과 이후 정정본의 대조다. 접수번호별 원본은 두 버전 각각의 입력 증거를 남길 수 있음.
- **검증 상태**: API 키가 없어 API 응답을 가져오지는 못함. 구현은 fixture 테스트로 parser만 확인.
- **결과**: 구현 경로는 마련됐으나 실제 수집·변경 팩트 확인은 보류.

## 구현 요약

- `src/opendart.py`: 요청 상한, 재시도, 키 포함 URL/예외 문자열 로그 회피.
- `src/revisions.py`: 정기보고서 파싱, 정정 표시, 날짜로 순서가 정해지는 원본·정정 쌍 탐색.
- `src/xbrl.py`: 접수번호별 ZIP XML을 파싱하고 numeric scale/sign을 적용.
- `src/db.py`, `sql/001_schema.sql`: PostgreSQL SCD Type 2 daterange 적재, 변경·추가·삭제 추적, PIT 쿼리 인덱스.
- `src/compare.py`: 팩트 delta, PIT 및 overwrite 대조군 로직.
- `src/benchmark.py`: 로컬 PostgreSQL에 통제된 합성 규모 데이터를 넣어 PIT 지연을 측정.
- 키 설정 파일은 `projects/wo-23-disclosure-lakehouse/.env`이며 Git 제외 규칙을 확인함. 전달 ZIP에는 `.env`와 OpenDART 원본을 제외할 것. 실제 API 결과 `results/experiment.json`이 생성되면 포함하고, 생성 전이면 없는 상태로 둘 것. 공개 가능한 합성 성능 결과 `results/benchmark.json`은 근거로 포함할 것.

## 실행·검증 기록

- Python 3.11 가상환경에서 `pytest -q`: **7 passed**.
- 테스트 중 접수일 parsing 결함을 발견해 수정한 뒤 전체 통과.
- Docker PostgreSQL 16 기동과 스키마 초기화를 확인. 호스트 기본 포트가 이미 사용 중이어서 프로젝트 DB 노출 포트를 `5434`로 조정.
- 실제 DB synthetic revision check: 원본 2행 적재, 정정 시 변경 1·삭제 1·삽입 2를 확인. 원본 시점 PIT는 이전 `Revenue=100`과 삭제 항목을, 정정 시점은 `Revenue=120`과 추가 항목을 반환. 검증 뒤 전용 `TESTWO23` 행을 삭제함.
- OpenDART live pull, 실제 접수번호의 PIT·overwrite 비교는 인증키 부재로 미실행.

## Claude 작업 범위

GitHub README와 Notion WO-23 케이스 스터디 초안을 작성할 때 Ship Gate를 완료로 표기하지 말 것. 실제 결과 JSON이 생기기 전에는 회사·접수번호·변경 팩트 수·실제 성능 수치를 만들지 말 것. 최종 공개용 문서는 CLAUDE.md의 시간 표현 금지, 원어 병기, 하단 용어집 규칙을 적용.
