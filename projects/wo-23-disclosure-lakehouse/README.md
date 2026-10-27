# WO-23 · 공시 레이크하우스

> **상태: 🔄 진행 중** — OpenDART 정정 이력 수집과 재현 구조를 구현했습니다. 실제 기업 정정 사례 검증과 성능 수치는 로컬 인증키가 준비된 뒤 확정합니다.

이 프로젝트는 정정될 수 있는 기업 공시를 이력으로 보존하는 레이크하우스(lakehouse)를 구현합니다. 최신 값만 저장하면 과거 분석에서 당시 공개되지 않았던 정보가 섞여 미래 정보 누수(look-ahead bias)가 발생할 수 있습니다. 이 프로젝트는 OpenDART 접수번호별 XBRL 원본을 보존하고, 정정 전후 값을 시점 기준으로 다시 조회할 수 있는 이력 저장소를 만듭니다.

## 증명하려는 질문

- 정정 전·후의 분기 재무정보를 point-in-time query(PIT)로 구분할 수 있는가?
- 이력 보존 방식과 최신 값 덮어쓰기(overwrite)는 과거 조회에서 어떤 차이를 만드는가?
- 테이블 규모가 커질 때 PIT 조회 지연은 어떻게 변하는가?

## 접근

1. OpenDART 공시목록에서 3개 상장사 후보의 정기보고서와 정정 표식을 찾습니다.
2. 공시 접수번호별 XBRL 원본을 내려받고 기업·기간·개념·문맥·단위별 재무 사실을 추출합니다.
3. PostgreSQL의 날짜 범위로 이전 값의 유효기간을 닫고 새 값·추가·삭제 이력을 저장합니다.
4. 같은 보고서의 정정 전·후 원본과 PIT 조회 결과를 대조하고, 덮어쓰기 대조군의 과거 오류를 계산합니다.
5. 인덱스가 있는 로컬 PostgreSQL에서 통제된 합성 행 수별 조회 지연을 측정합니다.

접수 원천이 제공하는 정밀도는 날짜이므로 유효기간도 날짜 단위입니다. 같은 날의 정정 순서를 임의로 정하지 않고 PIT 후보에서 제외합니다.

## Ship Gate

| 검증 항목 | 결과 | 근거 |
|---|---|---|
| 이력 적재 수·정정 변경·추가·삭제 건수 | ⬜ 실제 API 실행 대기 | `results/experiment.json` |
| 정정 전·후 PIT가 접수번호별 XBRL 원본과 일치 | ⬜ 실제 API 실행 대기 | `results/experiment.json` |
| SCD Type 2와 덮어쓰기의 과거 조회 차이 | ⬜ 실제 API 실행 대기 | `results/experiment.json` |
| 테이블 증가에 따른 쿼리 지연 | ✅ 1k: 0.163/0.283 ms · 10k: 0.266/0.365 ms · 50k: 0.757/1.049 ms (중앙값/P95) | `results/benchmark.json` |
| 오프라인 회귀 테스트 | ✅ 7개 통과 | `tests/` · Python 3.11 |

**측정 방식**: DB 성능은 로컬 PostgreSQL 16에서 합성 행 1k·10k·50k를 넣어 30회 측정한 PIT count 쿼리 중앙값입니다. 실제 공시 원본 대조는 OpenDART 키 입력 후 측정합니다.

## 실행

```bash
cp .env.example .env
# .env의 DART_API_KEY에 OpenDART 발급 키를 입력합니다.
docker compose up -d db
docker compose run --rm app
```

DB PIT 성능 벤치마크는 DB가 준비된 뒤 실행합니다.

```bash
docker compose run --rm app python -m src.benchmark
```

Python 3.11에서 로컬 테스트만 실행하려면:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

인증키는 `.env`에만 저장합니다. `data/`의 OpenDART 원본은 로컬에 보존하고 Git에서 제외합니다. 실제 실행 결과 `results/experiment.json`과 합성 성능 결과 `results/benchmark.json`은 재현 근거로 추적합니다. 요청 시도 횟수는 `MAX_API_REQUESTS`로 제한합니다.

## 데이터 출처

- [OpenDART 공시검색 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001) — 정정 표식과 접수번호가 포함된 공시목록
- [OpenDART 재무제표 원본파일(XBRL) API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019019) — 접수번호별 원본 아카이브

## 다음 단계

- OpenDART 키를 설정하고 실제 정정 사례를 수집합니다.
- SCD 적재 건수, 원본 일치 여부, overwrite 오류 수를 채웁니다.
- OpenDART 실제 정정 사례의 SCD 적재와 PIT·overwrite 결과를 측정합니다.
- 실행 결과를 근거로 Ship Gate와 Notion·GitHub 전달물을 확정합니다.

## 용어집

| 용어 | 뜻 |
|---|---|
| 공시 정정 (filing correction) | 이미 제출한 보고서의 내용을 바꾸는 후속 공시이며, 이 프로젝트에서는 이전 값과 새 값을 모두 추적하는 기준이다. |
| 시점 기준 조회 (point-in-time query, PIT) | 지정한 과거 시점에 유효했던 행만 읽는 방식으로, 과거 분석의 정보 시점을 재현한다. |
| 미래 정보 누수 (look-ahead bias) | 분석 시점 뒤에 알려진 정보를 과거 입력에 포함해 결과가 부풀려지는 오류다. |
| 이력 보존 (Slowly Changing Dimension Type 2, SCD Type 2) | 값이 바뀌면 이전 행의 유효기간을 닫고 새 행을 추가해 변경 이력을 남기는 패턴이다. |
| 덮어쓰기 (overwrite baseline) | 새 값으로 기존 값을 대체해 최신 상태만 남기는 비교 기준이며, 과거 값 재현을 잃는다. |
| XBRL (eXtensible Business Reporting Language) | 재무 개념과 보고 기간을 구조적으로 표현하는 공시 데이터 형식으로, 접수번호별 원본 사실을 비교하는 데 쓴다. |

## English Technical Summary

This project builds a point-in-time disclosure store from receipt-level OpenDART XBRL archives. PostgreSQL keeps revised financial facts with date-granular validity intervals, enabling comparisons between the original filing, its correction, and a latest-value overwrite baseline. Offline tests pass; live filing validation and query benchmarks remain pending until a local OpenDART API key is configured.
