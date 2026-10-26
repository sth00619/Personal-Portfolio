# 평가 프로토콜

## 데이터와 표본

- 데이터셋: BIRD Mini-Dev SQLite, 공식 Hugging Face 저장소의 고정 revision `f65faf4ae3b638c1fa6df1d3370c8d92c8366301`에서 받은 500문항.
- DB: BIRD 팀의 공개 `minidev.zip` 묶음. 질문 JSON과 DB는 각각 따로 배포되므로 두 파일의 SHA-256을 `source_manifest.json`에 남긴다.
- 200문항: simple/moderate/challenging 난이도별 66/67/67개. 난수 seed는 1607이다. BIRD 오류 분석 문헌에서 지적된 경계 조건을 점검하기 위해 ID 46, 62, 92를 같은 난이도 내 무작위 표본 항목과 교체해 포함한다. 표본은 모델 leaderboard 비교 목적이 아니라 이 프로젝트의 가드레일 전후 비교용이다.
- 원본 질문·DB 파일은 저장소에 포함하지 않는다. `download_data.py`가 공개 원본을 내려받으며, 결과는 `data/` 아래에만 저장한다.

## 모델 및 생성

- 모델: `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit`, revision `3dd939c621c08e5753d5b89f35a2642cd83b98ca`.
- Apple Silicon의 MLX 런타임에서 로컬 greedy decoding을 사용한다. API 자격 증명이나 유료 inference 호출은 필요하지 않다.
- 각 질문에 대해 기본 프롬프트와 스키마·증거 활용을 명시한 개선 프롬프트를 각각 실행한다. SQL 문자열 추출 외에는 의미를 자동 수정하지 않는다.

## 비교 단계

1. 기본 prompt + app guardrail 미적용
2. 기본 prompt + app guardrail 적용
3. 개선 prompt + app guardrail 적용

실행 계층에서는 모든 단계에 SQLite immutable/read-only 연결, query-only, VM step budget, 최대 10,000행 결과 한도를 둔다. 따라서 1단계는 애플리케이션 SQL 정책을 건너뛰지만 DB 파일 자체를 변경하지 않는 안전한 기준선이다. “가드레일 없음”을 실제 쓰기 권한을 연 데이터베이스에 대한 실험으로 해석하면 안 된다.

## 실행 정확도 (Execution Accuracy, EX)

Gold SQL과 예측 SQL을 각각 동일한 SQLite 파일에서 실행한다. 기본 Mini-Dev 공식 채점 코드에 맞춰 반환 행의 순서와 중복을 무시하는 set을 비교하고 float은 소수 둘째 자리로 반올림한다. projection alias/열 이름은 채점에 쓰지 않는다. SQL 문자열 일치율은 EX로 보고하지 않는다. SQL 생성 실패, 스키마 오류, 쿼리 제한 초과는 오답으로 계산한다.

## 가드레일과 오탐

- sqlglot으로 한 개의 구문상 유효한 query이며 SELECT 계열인지 확인한다. DDL/DML, 복수 statement, 제한된 위험 함수는 차단한다.
- SQLite `EXPLAIN QUERY PLAN`으로 테이블/컬럼 바인딩을 실행 전에 확인한다. read-only SQLite authorizer도 별도로 모든 비조회 동작을 거부한다.
- 최상위 LIMIT이 없으면 10,000을 붙이고, 더 큰 정수 LIMIT은 10,000으로 낮춘다. WHERE 없는 SELECT 및 query planner의 full scan은 경고로 기록한다.
- 실제 BIRD 생성 SQL에 대한 위험 시도/차단률을 집계한다. 생성 모델이 위험문을 내지 않는 경우 분모 0을 `null`로 보고한다. 별도 adversarial SQL corpus의 결과는 benchmark 생성 결과와 분리한다.
- 정상 SELECT 오탐은 기준선에서 정상 실행된 쿼리가 guardrail 적용 후 차단된 수로 센다.

## 데이터셋 정답 품질

CIDR 2026 분석은 BIRD Mini-Dev 498문항을 재검토해 52.8%에서 적어도 하나의 주석 오류 패턴을 확인했다. 이 수치는 해당 논문의 검토 집합과 분류 기준의 결과이며, 이 프로젝트의 200문항 오류율이나 최신 파일의 모든 gold가 틀렸다는 뜻은 아니다. 본 프로젝트에서는 알려진 사례 3개를 표본에 고정 포함하고, 평가 실패 최대 25건을 DB와 질문을 열어 별도로 판정한다. 의심과 확정을 구분하고 근거를 기록한다.

## 재현 커맨드

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python download_data.py
.venv/bin/python src/runner.py --limit 200
```

평가가 중단되면 `--resume` 옵션으로 저장된 항목을 이어간다. `--limit`은 최종 200문항을 기본으로 하며, 결과 비교 시 해당 설정을 함께 기록한다.

## 라이선스 및 참고 문헌

- BIRD Mini-Dev 공식 안내: https://github.com/bird-bench/mini_dev
- BIRD Mini-Dev 데이터 카드 및 CC BY-SA 4.0 표기: https://huggingface.co/datasets/birdsql/bird_mini_dev
- BIRD 데이터 안내·이용 조건: https://bird-bench.github.io/
- 사용 모델 카드와 `qwen-research` 라이선스 표기: https://huggingface.co/mlx-community/Qwen2.5-Coder-3B-Instruct-4bit
- Tengjun Jin, Yoojin Choi, Yuxuan Zhu, Daniel Kang, “Text-to-SQL Benchmarks are Broken: An In-Depth Analysis of Annotation Errors,” CIDR 2026: https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf
