# WO-16 · Text-to-SQL 에이전트와 가드레일(Guardrail)

> 개인 프로젝트 · 대응 직군: AI Agent / Data PM · 데이터: BIRD Mini-Dev, CC BY-SA 4.0 표기 · 모델: Qwen Research License

## 문제 정의

자연어-SQL 변환(Text-to-SQL) 모델은 존재하지 않는 스키마(schema)를 참조하거나 데이터 변경 SQL을 내놓을 수 있습니다. 모델 답변을 데이터베이스에 보내기 전 구문·권한·비용 한도를 확인하고, 그 과정에서 정상 조회 질의를 얼마나 잃는지도 측정합니다.

## 가설

SELECT 전용 정책, 스키마 사전 확인, 읽기 전용 SQLite 실행을 겹쳐 적용하면 이 평가의 위험 SQL을 차단할 수 있습니다. 제한된 프롬프트 개선은 실행 정확도를 올릴 수 있지만, 가드레일만으로 SQL 의미 오류가 해결되지는 않으므로 실행 정확도와 정상 SELECT 오탐을 동시에 봅니다.

## 접근 — 시도 순서

1. 기본 프롬프트가 만든 SQL을 애플리케이션 가드레일 없이 실행해 기준선(baseline)을 잡습니다.
2. DB 파일은 처음부터 SQLite immutable/read-only로 열고 쓰기 authorizer와 실행 예산을 둡니다. 앱 정책을 끈 기준선에서도 원본 DB는 변경되지 않습니다.
3. `sqlglot` SELECT 정책, SQLite query-plan 스키마 확인, LIMIT 및 전체 스캔(full scan) 경고를 추가합니다.
4. 스키마 참조·조인 키·질문 evidence 활용을 명시한 프롬프트를 재측정하고, 난이도·실패 유형·gold 의심 사례를 분리합니다.
5. 공개 재검토 논문에서 지적된 gold 경계 문항을 포함하고, 실행 결과와 주석 의미를 따로 검토합니다.

## 데이터

11개 SQLite 데이터베이스를 포함한 BIRD Mini-Dev 500문항 중 난이도별 층화 표본(stratified sample) 200문항을 사용합니다. seed는 `1607`이며 simple/moderate/challenging은 66/67/67문항입니다. 공개 주석 오류 검토에서 거론된 ID 46·62·92를 같은 난이도 항목과 교체해 포함했습니다. 질문 JSON은 [Hugging Face 데이터 카드](https://huggingface.co/datasets/birdsql/bird_mini_dev)의 고정 revision에서 받고 SQLite DB 묶음은 [BIRD 공식 Mini-Dev 저장소](https://github.com/bird-bench/mini_dev)의 공개 파일에서 받아 SHA-256을 기록합니다. 모델은 [Qwen 3B 4-bit 카드](https://huggingface.co/mlx-community/Qwen2.5-Coder-3B-Instruct-4bit) revision을 고정했습니다. 원본 데이터는 저장소에 커밋하지 않습니다.

데이터 카드에는 CC BY-SA 4.0, 모델 카드에는 `qwen-research` 라이선스가 표시되어 있습니다. [출처 장부](docs/source_manifest.json)와 [평가 프로토콜](docs/benchmark_protocol.md)의 원문 링크를 확인하세요.

## 파이프라인

`질문 + 스키마 + 근거(evidence) → 로컬 SQL 생성 → SQL 정적 검사 → SQLite query plan(실행 계획)으로 스키마 compile → 읽기 전용 실행 → Gold SQL 결과와 공식 EX 기준 행 set(집합) 비교 → 실패 및 안전 지표 집계`

실행 정확도(Execution Accuracy, EX)는 Gold SQL과 예측 SQL의 실제 결과 행을 비교합니다. 행 순서와 중복을 무시하고 float은 소수 둘째 자리로 반올림하며 SQL 문자열 비교는 사용하지 않습니다. 평가 기준과 위험 경계는 [프로토콜](docs/benchmark_protocol.md)에 있습니다.

## 실행

모델 추론은 Apple Silicon의 MLX에서 실행하고, 저장된 SQL 결과 재채점은 Docker Compose의 CPU 컨테이너에서도 수행할 수 있습니다.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python download_data.py
.venv/bin/python src/runner.py --limit 200

docker compose run --build --rm score
```

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---:|---:|
| 기본 프롬프트 실행 정확도 (Execution Accuracy, EX) | 실행 가능 gold 전체 | 56/196 (28.57%) |
| 기본 프롬프트 + 앱 가드레일 EX | 차단·오탐 동시 집계 | 56/196 (28.57%) |
| 개선 프롬프트 + 앱 가드레일 EX | 난이도별 분해 | 63/196 (32.14%; +3.57%p) |
| 생성 위험 SQL 차단율 | 위험 생성 시도 전부 집계 | 1/1 (100%) |
| 별도 공격 SQL 정적 차단율 | 10개 사례 | 10/10 (100%) |
| 정상 SELECT 오탐 | 실제 정상 실행된 쿼리 기준 | 0건; 고정 benign set 0/3 |
| gold 실행 오류 | 별도 제외 건수 공개 | 4/200 (EX 분모에서 제외) |
| 실패 표본 수동 판정 | 25개 오답 후보 | 모델 오류 20건, gold 의심 동반 5건 (20%); 별도 경계 사례 ID 92 |

**측정 방식**: Qwen 3B 4-bit 로컬 그리디 디코딩(greedy decoding), SQLite immutable/read-only 실행, 공식 EX 기준 결과 행 set 비교. 난이도별 개선 프롬프트+가드레일 EX는 challenging 11/65 (16.92%), moderate 24/65 (36.92%), simple 28/66 (42.42%)입니다. 핵심 수치는 [재채점 결과](artifacts/metrics.json)에 기록합니다.

## 시행착오와 의사결정

- MLX-LM 설치 버전에서 `temp` 인자가 지원되지 않아 첫 추론이 중단됐습니다. 해당 API의 sampler를 사용한 greedy decoding으로 바꿔 평가를 재개했습니다.
- gold query 하나가 2M SQLite VM step 예산에서 중단됐습니다. 예산을 20M으로 올리고, 그래도 실행되지 않는 gold는 모델 오답과 합치지 않고 EX 분모에서 별도 제외하도록 평가를 수정했습니다.
- BIRD 질문 JSON과 DB 아카이브는 독립적으로 배포되고 내부 JSON 해시도 달랐습니다. 각각의 원본·revision·SHA-256을 기록하고, gold 실행 오류를 데이터 정합성 지표로 분리했습니다.
- Python SQLite 연결의 `with` 문이 파일 핸들을 닫지 않는 것을 실행 중 발견했습니다. `contextlib.closing`으로 명시 폐기해 체크포인트 이후 평가를 안전하게 재개했습니다.

## 측정 경계 (한계)

표본은 BIRD 전체 리더보드와 직접 비교할 용도가 아닙니다. 가드레일 적용 전후의 상대 비교와 난이도별 실패를 읽습니다. 25개 실패 후보를 수동 검토한 결과 5개에서 모델 오류와 gold 질문/evidence/SQL 경계 의심이 함께 발견됐고, 실패 후보 밖의 ID 92도 별도 경계 사례로 기록했습니다. 이는 이 표본의 일반적인 gold 오류율 추정치가 아닙니다. 공개 재검토 연구에서 확인한 BIRD Mini-Dev 주석 오류는 연구팀의 검토 기준에 따른 결과이며, 이 표본의 오류율로 그대로 적용하지 않습니다. 세부 판정과 근거는 [수동 검토표](docs/manual_review.md), [판정 데이터](docs/manual_review_verdicts.json), [gold 감사](docs/annotation_audit.md)를 확인하세요.

**다음 단계**: 실패 유형별 질문 근거(evidence) 검색·스키마 축소 전략을 적용해 재평가.

## 개발 방식 (AI 활용 구분)

| 사용자 지정 | Codex가 생성한 것 |
|---|---|
| WO-16 범위와 Ship Gate, 포트폴리오용 프로젝트 목표 | 다운로드·평가·가드레일·재채점 코드와 문서 초안 |
| 별도 기술 선택을 지정하지 않음 | 로컬 모델·버전·표본·안전 한도 선택과 근거 기록 |

## 용어집

| 용어 | 뜻 |
|---|---|
| 가드레일 (Guardrail) | 생성 SQL을 DB 실행 전에 검사하고 허용 범위로 제한하는 정책입니다. |
| 골드 SQL (Gold SQL) | 벤치마크가 비교용 정답으로 제공하는 질의입니다. |
| 오탐 (False Positive) | 허용 가능한 SELECT를 가드레일이 잘못 차단한 경우입니다. |
| 실행 정확도 (Execution Accuracy, EX) | 두 SQL을 DB에서 실행해 반환 결과가 같은지 세는 점수입니다. |
| 전체 스캔 (Full Scan) | 실행 계획(query plan)이 인덱스 없이 테이블을 읽는 경로로, 느린 질의의 위험을 경고합니다. |
| 층화 표본 (Stratified Sample) | 난이도별 문항 수를 정해 추출한 평가 부분집합입니다. |

## English Technical Summary

WO-16 evaluates a local Text-to-SQL pipeline on a difficulty-stratified 200-question BIRD Mini-Dev subset. It compares baseline generation, baseline generation with SQL guardrails, and a schema-grounded prompt with guardrails. Execution accuracy follows Mini-Dev’s unordered set comparison and two-decimal float normalization rather than SQL string matching. Static SQLGlot checks, SQLite schema compilation, read-only authorizers, row and VM-work limits, and full-scan warnings make the evaluation safe to run against benchmark databases. Known annotation ambiguities are reviewed separately from model errors.
