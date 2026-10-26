# WO-16 Claude 전달 핸드오프

## 작업 범위

사용자 요청은 WO-16 시작 파일에 맞춰 프로젝트 16을 진행하는 것이다. 데이터 변환 에이전트, 실행 안전층, 실행 정확도 비교, 오류 검토 자료를 전용 폴더 `projects/wo-16-text-to-sql-guardrails/`에 구성했다. GitHub 루트 README와 Notion은 이 작업에서 수정하지 않는다.

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| 원본을 변경하지 않고 모델 SQL을 비교할 수 있다 | `src/guardrails.py`, `src/runner.py`, `src/score.py`; 세 단계 모두 immutable/read-only SQLite와 authorizer를 사용 | 200문항 세 단계 평가 완료 | 사용자가 안전·정확도 평가를 요청; Codex가 격리 방식 구현 및 실행 | 확인됨 |
| 가드레일이 데이터셋 생성 위험 SQL과 별도 공격 질의를 차단한다 | `src/guardrails.py`; `artifacts/metrics.json`의 unsafe SQL 및 adversarial 지표 | 위험 생성 1/1, 정적 공격 10/10 차단; benign false positive 0/3 | 작업지시서 요구; Codex가 검사와 고정 공격 corpus 구현 | 확인됨 |
| 난이도별 200문항 비교가 재현 가능하다 | seed `1607`, 66/67/67 quota, ID 46·62·92 고정 포함; `src/runner.py`; 평가 JSONL | 200개 생성, 실행 가능 gold 196개; baseline 56/196, improved+guard 63/196 | Codex가 공개 데이터 버전 차이를 확인하고 표본 규칙 결정 | 확인됨 |
| gold SQL에는 실행 점수로 드러나지 않는 주석 경계 문제가 있다 | `docs/annotation_audit.md`; 질문·DB 스키마·직접 실행 결과; CIDR 공개 분석 논문 | ID 28·46·62·92·881·1175를 각각 대조하고 세부 근거 기록 | 작업지시서가 수동 gold 검토 요청; Codex가 사례 선정·교차확인 | 확인됨 |
| 기준선 실행 제한은 단순 모델 오류로 섞지 않아야 한다 | 첫 10문항 이후 2M VM budget에서 gold 쿼리 `SQLITE_INTERRUPT`; `MAX_VM_STEPS=20_000_000`; gold 실행 오류 분리 | 최종 gold 제외 수는 산출 후 기입 | Codex가 실행 로그를 보고 예산 및 분모 정의 수정 | 확인됨 |

## 판단 장면

### 1. 모델 실행 방식: 외부 API 대신 로컬 MLX

- **관측**: 사용 가능한 `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `HF_TOKEN` 환경 값이 없었다. Apple Silicon 16GB 메모리와 Python 3.11이 확인됐다.
- **결정**: Qwen2.5-Coder-3B-Instruct-4bit MLX 버전을 모델 저장소 revision으로 고정해 로컬 실행한다. 별도 API 호출과 비용을 만들지 않으며, 재현에 필요한 모델 revision을 기록한다.
- **예상과 달랐던 점**: 첫 추론에서 설치한 mlx-lm 버전은 `temp` keyword를 받지 않아 중단됐다. 버전 API에 맞춰 sampler 기반 greedy decoding으로 바꾸고 checkpoint를 재개했다.
- **근거**: `requirements.txt`, `src/runner.py`, `docs/source_manifest.json`, 실제 `artifacts/evaluation.jsonl`.
- **역할**: 모델/API 선택은 Codex 판단. 사용자는 로컬/호스팅 선택을 지정하지 않았다.

### 2. Gold 실행 오류와 DB 안전성 분리

- **관측**: 기본 2,000,000 SQLite VM step 제한이 정상 gold 쿼리의 실행도 `interrupted`로 끝냈다. 초기 실행은 12개 checkpoint 이후 멈췄다.
- **결정**: 한도를 20,000,000으로 올리고, 재실행 가능한 JSONL checkpoint에서 이어갔다. gold query 자체가 실행되지 않는 항목은 각 stage의 EX 분모에서 제외하고 `gold_execution_errors`에 따로 계상한다.
- **이유**: gold가 실행되지 않으면 모델의 결과와 일치 여부를 판단할 수 없다. 이를 오답으로 세면 모델 오류와 평가 환경/정답 데이터 문제를 합친다.
- **추가 관측**: 70문항 checkpoint에서 SQLite 연결 파일 핸들이 남는 것도 확인했다. Python의 sqlite connection `with`는 파일을 닫지 않아 `contextlib.closing`으로 폐기하도록 바꾸고 checkpoint부터 재개했다.
- **역할**: 실행 로그와 열린 파일 핸들에 따라 Codex가 예산·분모·연결 해제 정책을 수정했다.

### 3. BIRD의 주석 신뢰도와 실행 일치의 경계

- **관측**: 질문 JSON(Hugging Face 고정 revision)과 공식 DB 아카이브의 포함 JSON이 서로 다른 SHA-256을 가졌다. CIDR 2026 논문은 BIRD Mini-Dev 498문항을 검토해 52.8%에서 하나 이상의 주석 오류를 보고했다. 이 연구 비율은 본 표본에 전용하지 않았다.
- **결정**: 질문 데이터와 DB 아카이브 각각의 URL, revision, SHA-256을 남긴다. ID 46·62·92를 난이도 층화 표본에 넣고, 무작위 표본에 들어간 ID 881·1175도 known-issue 사례로 감사한다. EX는 공식 Mini-Dev 기준처럼 두 자리 float 정규화 후 중복·순서 무관 행 set으로 계산하고 주석 오류 의심은 별도 기록한다.
- **직접 확인한 근거**: ID 28은 질문의 15–17세를 evidence와 gold가 Ages 5–17로 바꾸고 DB에는 15–17 열이 없다. ID 46·62 질문은 grades 1–12를 묻지만 gold가 `Enrollment (K-12)`를 사용한다. ID 62 DB에는 K-12와 Ages 5-17 열만 있다. ID 92는 `>6000 and <10000` 대신 양끝을 포함하는 `BETWEEN`을 쓰지만 실행 결과는 둘 다 69다. ID 881의 Race 460은 29행 중 `+1/+2/+3 Laps` 12행이 `time=NULL`; Gold식은 17.24%, 상태 기준은 58.62%다. ID 1175는 evidence가 Examination Date를 말하지만 gold는 Laboratory.Date를 쓰고 두 diagnosis 열도 존재한다.
- **역할**: 사용자 요청은 WO-16 수행; 데이터 스냅샷과 수동 감사 항목 선택은 Codex 판단.

## 실행 결과

전체 200문항 실행과 공식 EX 기준 재채점을 완료했다. Docker Compose scorer도 동일한 지표를 재현했다.

- 기준 프롬프트 EX / guard 적용 EX / 개선 프롬프트+guard EX: 56/196 (28.57%) / 56/196 (28.57%) / 63/196 (32.14%), +7건·+3.57%p.
- 실제 모델 위험 SQL 생성 수 / 차단 수 / 차단율: 1 / 1 / 100%.
- 고정 adversarial SQL 정적 차단 결과: 10/10 (100%); benign SELECT 0/3 false positive.
- 정상 SELECT 오탐: 평가된 일반 질의에서 0건.
- 난이도별 개선+guard EX: challenging 11/65 (16.92%), moderate 24/65 (36.92%), simple 28/66 (42.42%).
- 실패 유형(자동 휴리스틱): schema misunderstanding 60, join heuristic 51, aggregation heuristic 13, syntax 4, denotation 3, other execution 2. 분류는 겹칠 수 있는 규칙 기반 진단이다.
- gold SQL 실행 제외 수: 4/200.
- 수동 검토 25개 결과: 모델 오류 20건, gold 의심 동반 5건(20%), 판정 불가 0건. ID 92는 실패 표본 밖의 별도 gold 경계 사례.

## 수동 데이터 검토

`docs/manual_review.md`에는 실행 실패 후보가 들어간다. 25개 후보 전부의 질문·evidence·Gold SQL·예측 SQL·실행 진단을 DB 스키마와 결과로 확인했다. 재현 시 판정은 `docs/manual_review_verdicts.json`에서 읽어 표와 metrics에 반영된다. 알려진 6개 gold 경계 사례의 구체적 설명은 `docs/annotation_audit.md`에 별도로 쌓았다.

## SONG의 결정 및 Claude 전달 요청

- 사용자가 명시한 결정: WO-16을 시작하라고 요청함.
- 사용자가 정하지 않은 항목(로컬 모델, 정확한 표본 규칙, SQL 실행 제한)은 Codex가 선택하고 위 근거를 남김.
- Claude에게 요청: `README.md`와 `CLAUDE_HANDOFF.md`, 결과표, 재검수 사례를 바탕으로 GitHub README 및 기존 Notion WO-16 페이지를 갱신한다. 수치와 gold 의심 판정은 별도 라벨로 표현하고, BIRD와 Qwen 라이선스 표기를 출처와 대조한다.
