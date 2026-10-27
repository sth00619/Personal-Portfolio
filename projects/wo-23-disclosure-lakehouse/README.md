# WO-23 · 공시 레이크하우스

> **상태: ✅ 완료** — 실제 분기 정정 사례를 적재하고, 정정 전·후 시점 기준 조회와 덮어쓰기 대조군을 원본 XBRL과 비교했습니다.

이 프로젝트는 정정될 수 있는 기업 공시를 이력으로 보존하는 레이크하우스(lakehouse)를 구현합니다. 최신 값만 저장하면 과거 분석에 당시 공개되지 않았던 정보가 섞여 미래 정보 누수(look-ahead bias)가 발생할 수 있습니다. OpenDART 접수번호별 XBRL(eXtensible Business Reporting Language) 원본을 보존해 보고서가 정정되기 전과 후의 값을 다시 조회합니다.

## 증명하려는 질문

- 정정 전·후의 분기 재무정보를 시점 기준 조회(point-in-time query, PIT)로 구분할 수 있는가?
- 이력 보존 방식과 최신 값 덮어쓰기(overwrite)는 과거 조회에서 어떤 차이를 만드는가?
- 테이블 규모가 커질 때 PIT 조회 지연은 어떻게 변하는가?

## 접근

1. 분기 공시의 정정 표식과 접수번호를 검색하고 숫자 재무 팩트 변경이 있는 사례를 선정합니다.
2. 접수번호별 XBRL 원본에서 숫자 팩트를 읽습니다. 원천 문맥 식별자(context ID)를 보존해 같은 기간·차원으로 보이는 분기값과 누적값을 구분하고, 영문·한글 설명 텍스트는 수치 적재에서 제외합니다.
3. PostgreSQL의 날짜 범위로 이전 값의 유효기간을 닫고 새 값·추가·삭제 이력을 저장합니다.
4. 정정 전·후 원본과 PIT 결과를 대조하고, 최신 값만 남기는 대조군의 과거 값 오류를 셉니다.
5. 로컬 PostgreSQL에서 통제된 합성 행 수별 PIT 조회 지연을 측정합니다.

접수 원천이 제공하는 정밀도는 날짜이므로 유효기간도 날짜 단위입니다. 같은 날 접수된 정정의 순서는 임의로 정하지 않습니다.

## 실제 표본

아이티센씨티에스의 분기보고서 한 건에서 원본 숫자 재무 팩트(financial fact) 544개와 정정본 542개를 읽었습니다. 정정본은 기존 팩트 6개의 값을 바꾸고 2개를 제거했습니다. 변경 없이 유지된 팩트는 536개였습니다.

| Ship Gate | 관측값 | 근거 |
|---|---|---|
| 원본·정정본 적재 및 변경 수 | 원본 544개, 정정본 542개, 변경 6개, 추가 0개, 삭제 2개 | `results/experiment.json` |
| PIT 결과와 실제 XBRL 원본 일치 | 원본 시점 544/544, 정정 시점 542/542 일치 | `results/experiment.json` |
| 덮어쓰기 대조군의 과거 조회 차이 | 원본 값 8개를 재현하지 못함 | `results/experiment.json` |
| 테이블 증가에 따른 쿼리 지연 | 1k: 0.163/0.283 ms · 10k: 0.266/0.365 ms · 50k: 0.757/1.049 ms (중앙값(median)/95백분위수(P95)) | `results/benchmark.json` |
| 자동화 테스트 | Python 3.11 및 Docker 환경에서 8개 통과 | `tests/` |

**측정 방식**: 공시 팩트와 PIT 대조는 OpenDART 원본 및 로컬 PostgreSQL 16으로 검증했습니다. 성능 행 수는 합성이며, 각 규모에서 로컬 연결 쿼리를 30회 측정했습니다.

## 재현

```bash
cp .env.example .env
# .env의 DART_API_KEY에 OpenDART 발급 키를 입력합니다.
docker compose up -d db
docker compose run --rm app
```

성능 벤치마크를 다시 실행하려면 PostgreSQL 서비스를 올린 뒤 실행합니다.

```bash
docker compose up -d db
docker compose run --rm app python -m src.benchmark
```

Python 3.11에서 테스트를 실행하려면:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

인증키는 `.env`에만 저장합니다. 기업코드와 접수번호별 XBRL 원본은 `data/`에 보존하고 Git에서 제외합니다. 집계 결과와 성능 측정값은 `results/`에서 확인할 수 있습니다. API 요청 상한은 `MAX_API_REQUESTS`로 제어합니다.

## 데이터 출처

- [OpenDART 공시검색 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001) — 정정 표식과 접수번호가 포함된 공시목록
- [OpenDART 재무제표 원본파일(XBRL) API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019019) — 접수번호별 원본 아카이브

## 다음 단계

- 여러 기업의 재무제표 분류체계(taxonomy) 확장 개념을 표준 계정으로 정규화합니다.
- 같은 날 접수된 정정의 시각 정밀도를 확보할 수 있는 원천과 규칙을 조사합니다.

## 용어집

| 용어 | 뜻 |
|---|---|
| 공시 정정 (filing correction) | 이미 제출한 보고서의 내용을 바꾸는 후속 공시이며, 이 프로젝트에서는 이전 값과 새 값을 모두 추적하는 기준이다. |
| 시점 기준 조회 (point-in-time query, PIT) | 지정 시점에 유효했던 행만 읽어 과거 분석의 정보 시점을 재현하는 방식이다. |
| 미래 정보 누수 (look-ahead bias) | 분석 시점 뒤에 알려진 정보를 과거 입력에 포함해 결과가 부풀려지는 오류다. |
| 이력 보존 (Slowly Changing Dimension Type 2, SCD Type 2) | 값이 바뀌면 이전 행의 유효기간을 닫고 새 행을 추가해 변경 이력을 남기는 패턴이다. |
| 덮어쓰기 (overwrite baseline) | 새 값으로 기존 값을 대체해 최신 상태만 남기는 비교 기준이며, 과거 값 재현을 잃는다. |
| 문맥 식별자 (XBRL context ID) | 사실의 보고 기간과 차원을 가리키는 원천 키이며, 이 프로젝트에서는 분기와 누적값을 구분하는 데 사용한다. |
| 분류체계 (taxonomy) | 기업별 확장 개념을 공통 재무 계정으로 연결하는 정의 모음이며, 다음 단계에서 회사 간 비교를 가능하게 한다. |
| 재무 팩트 (financial fact) | XBRL 문맥에 매달린 계정 값 한 건이며, 정정 전후 비교의 기본 단위다. |
| 중앙값 (median) | 측정값을 순서대로 놓았을 때 가운데 값이며, 반복 조회 성능을 요약한다. |
| 95백분위수 (95th percentile, P95) | 측정값의 95%가 이 수치 이하인 지점이며, 지연 분포의 높은 쪽을 보여준다. |
| XBRL (eXtensible Business Reporting Language) | 재무 개념과 보고 기간을 구조적으로 표현하는 공시 데이터 형식이다. |

## English Technical Summary

This project stores receipt-level OpenDART XBRL facts in PostgreSQL with date-granular SCD Type 2 validity. An actual quarterly correction was used to verify original and corrected point-in-time results against both source filings. The overwrite baseline failed to reproduce eight historical fact values. Query latency was measured separately on synthetic table sizes in a local PostgreSQL 16 container.
