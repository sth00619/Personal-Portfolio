# WO-20 전달 메모

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| 공식 SQuAD 2.0 dev 파일을 고정했다 | `data/download.py`; 로컬 `data/squad_v2_dev.json` | 4,370,528 bytes; SHA-256 `80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8` 일치 | 작업지시서가 데이터셋 지정; Codex가 다운로드·해시 확인 | 확인됨 |
| dev split을 문항 단위로 읽고 세그먼트를 분리했다 | `src/dataset.py`, `tests/test_dataset.py`; 컨테이너 pytest 출력 | 11,873문항, answerable 5,928, unanswerable 5,945; 10 tests passed | Codex가 로더 구현·시험; 사용자는 결과를 아직 별도 판단하지 않음 | 확인됨 |
| 답변 생성과 통계 분석을 재현 가능하게 만들었다 | `src/prompts.py`, `src/experiment.py`, `src/evaluation.py`, `src/scoring.py`; pytest 출력 | 결정적 층화 표본·JSONL 재개·EM/F1·paired t-test·bootstrap·Holm·사후 power 산출 코드 구현 | Codex가 구현·단위 시험; inference endpoint 호출은 미실행 | 일부 |
| 모델 품질과 judge의 일치 결과를 얻었다 | `results/` 출력 예정; 현재 결과 파일 없음 | 실제 API 생성·judge 0건; 품질 지표 미측정 | API 모델/자격 증명 미설정; 사용자가 선택할 때까지 실행 보류 | 근거 없음 |
| 300문항 균형 표본을 대안으로 검토했다 | `.env.example` 이력, `src/dataset.py`, README 비용 규모 설명 | 대안은 150 answerable + 150 unanswerable; A/B 생성 최대 600회와 judge 30회 | Codex가 비용 대안을 비교했고 사용자가 전체 split을 선택 | 확인됨 |
| 전체 실행을 $10 이내로 제한할 수 있는 구성을 마련했다 | SQuAD 원문 바이트 산출; `src/llm.py` `CostBudget`; `results/budget_reservations.json` | 전체 23,746 답변 요청+30 judge; UTF-8 byte를 입력 토큰 상한으로 쓴 예상 예약 상한 약 $4.4788; 실행 상한 $8 | 사용자가 OpenAI API·전체 세트·$10 이하를 요청; Codex가 `gpt-6-luna` 현행 공개 가격 기준을 선택하고 로컬 가드 구현 | 일부 |

## 판단 장면

### 원본 데이터 형식과 파서 가정

- 상태: 이번 작업에서 실제로 검증
- 맥락: 공식 JSON의 `answers` 필드는 일반 JSON dict처럼 보이지만 Hugging Face `datasets` JSON 로더를 거치면서 answer record 목록 형태로 표현될 수 있었다.
- 첫 가설: 원본의 `{text, answer_start}` 구조를 그대로 읽으면 된다고 가정했다.
- 대안: 원본 JSON을 직접 순회하거나 `datasets`의 정규화 결과 양쪽을 지원한다.
- 판단 기준: 지정 기술 스택을 유지하면서 원본과 정규화된 표현을 모두 정확히 처리하는가.
- 실험: 실제 dev 파일을 로드하고 `docker compose run --build --rm test`에서 전체 데이터셋 수와 answerable/unanswerable 수를 검증했다.
- 관측: 첫 로더는 `answers` 타입 가정으로 테스트에 실패했다. dict와 list를 모두 처리하도록 수정한 뒤 10개 테스트가 통과했다. 전체는 11,873문항(5,928/5,945)으로 확인했다.
- 뜻밖의 결과: 로더 라이브러리가 answer 필드를 정규화해 코드의 입력 형태가 원본 JSON과 달랐다.
- 결정: 두 표현을 모두 받도록 로더를 보완했다. 구현·수정·재시험은 Codex가 수행했다.
- 한계: 허용한 구조는 현재 원본과 사용 라이브러리 결과를 위한 것이며, 임의의 SQuAD 변형까지 지원한다고 주장하지 않는다.

### 실험 규모와 비용 상한

- 상태: 사용자가 OpenAI API, 전체 split, $10 이하 조건을 선택; 모델·가드 구현은 Codex가 판단
- 맥락: 전체 dev 11,873문항에 A/B를 각각 실행하면 생성 호출만 23,746회이며 judge 호출이 추가된다.
- 첫 가설: 전체 split 실행이 가장 강한 결과를 제공한다.
- 대안: 즉시 전체 실행, 300문항 균형 표본 실행, 전체 실행에 보수 비용 가드를 두는 방법을 비교했다.
- 판단 기준: 결과의 해석 가능성과 사용자가 부담하는 호출량·비용을 함께 고려한다.
- 실험: 공식 원본으로 전체 질문의 input prompt UTF-8 바이트 수를 합산하고 요청당 512바이트 프로토콜 여유와 96 output token 최대치를 더했다. 현재 공식 `gpt-6-luna` 단가를 적용했고, 각 재시도 전에 호출별 최악 예약액을 저장해 로컬 $8에서 차단하도록 했다.
- 관측: 11,873건의 A/B 입력 바이트 합계는 21,202,614 bytes다. judge 요청 30건까지 포함한 23,776회 입력의 보수 추정은 33,375,926 토큰 상한, 최대 출력 예약은 2,282,496토큰이며, 입력 $0.10/백만·출력 $0.50/백만 기준 합계 약 $4.4788다.
- 뜻밖의 결과: 작업지시서에는 답변 불가능 비율이 약 1/3이라고 적혀 있지만 고정된 파일의 실제 구성은 5,945/11,873, 약 50%였다.
- 결정: 사용자는 전체 set과 $10 이하 조건을 선택했다. Codex는 전용 OpenAI project hard limit $8와 앱 내부 persistent reservation cap $8을 권장하고 `gpt-6-luna`로 설정했다. 사용자가 발급받은 키는 로컬 `.env`에 직접 추가하도록 했다.
- 한계: 실제 가격·모델 품질·검정력은 모델과 응답 결과가 없으므로 아직 알 수 없다.

### Ship Gate 지표의 해석 범위

- 상태: 구현에 반영; 실측 대기
- 맥락: 전체 평균만으로는 답변 불가능 질문의 abstention 품질과 답변 가능한 질문의 불필요한 거부가 가려질 수 있다.
- 첫 가설: Prompt B의 `NO_ANSWER` 규칙은 불가능 문항을 더 잘 다루지만 answerable에서 false abstention이 늘 수도 있다.
- 대안: 하나의 전체 F1만 비교하거나, EM/F1과 두 세그먼트 및 abstention 지표를 모두 비교한다.
- 판단 기준: 작업지시서의 가장 강한 질문(소표본·전체 판단 차이, 자동 점수·judge 일치, 세그먼트 차이)을 직접 관찰할 수 있는가.
- 실험: 같은 질문을 두 prompt에 넣는 코드와 지표·paired 통계·30건 judge 분석을 구현하고 mock/단위 테스트를 실행했다. 실제 모델 응답은 생성하지 않았다.
- 관측: 코드 경로와 단위 테스트는 확인됐다. `results/`는 비어 있어 성능 수치가 없다.
- 결정: 성능표를 실행 대기로 표시하고 관측 결과처럼 꾸미지 않는다. 지표 구현은 Codex가 했고 결과 해석 및 prompt 채택은 아직 이뤄지지 않았다.
- 한계: 소수 judge 표본의 κ·상관은 불확실성이 크며, judge가 생성 모델과 독립적인 평가자인지도 모델 선택에 달려 있다.

## 사용자 의사결정 지점

사용자는 OpenAI API, 전체 dev split, $10 이하 예산 한도를 선택했다. Codex가 공개 토큰 단가를 기준으로 `gpt-6-luna`를 설정했다. 사용자는 키를 채팅에 보내지 않고 프로젝트 로컬 `.env`에 직접 설정한다. OpenAI의 hard spend limit은 추적·차단 집계가 약간 늦을 수 있어, $8 프로젝트 한도와 로컬 호출 전 예약 상한을 함께 사용한다.

## 실행 및 검증 상태

- 컨테이너 pytest: 11 passed. 데이터셋 통합 검증과 예산 초과 차단·재개 시험을 포함한다.
- 공식 파일 크기·SHA-256: 확인됨.
- `docker compose config --quiet`: exit 0.
- `python3 -m py_compile src/*.py data/download.py`: exit 0.
- `git check-ignore data/squad_v2_dev.json .env`: 데이터와 로컬 키 파일 경로가 ignore 규칙에 매치됨.
- OpenAI Chat Completions 요청 형식: mock 기반 시험만 수행; 실제 endpoint 호출은 없음.
- 실제 성능·judge·토큰·비용 결과: 미측정. `results/` 출력은 API 실행 후 생성된다.

## Claude가 이어서 할 일

1. API 실행 후 `results/experiment_results.json`, `results/judge_summary.json`, `results/sample_size_power.csv`를 확인해 Ship Gate 수치와 표본 경계를 README에 반영한다.
2. 30건 judge 결과를 자동 F1과 비교하되, 상관·일치 수치만으로 사람 평가의 대체라고 주장하지 않는다.
3. 루트 README·Notion 갱신 시 이 근거 장부와 판단 장면을 활용하고, 시간 표현 및 근거 없는 성능 주장을 추가하지 않는다.
