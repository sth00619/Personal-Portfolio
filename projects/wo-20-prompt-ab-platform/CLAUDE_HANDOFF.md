# WO-20 전달 메모

## 근거 장부

| 주장 후보 | 코드·결과 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| 공식 SQuAD 2.0 dev 파일을 고정했다 | `data/download.py`; `tests/test_dataset.py` | 4,370,528 bytes; SHA-256 `80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8` 일치 | 작업지시서가 데이터셋 지정; Codex가 다운로드·해시 확인 | 확인됨 |
| 전체 평가셋을 동일 모델로 A/B 생성했다 | `results/experiment_results.json` metadata, `results/predictions.jsonl` 로컬 캐시 | 11,873문항; A/B 23,746 응답; answerable 5,928, unanswerable 5,945; 모델 `gpt-6-luna` | 사용자가 OpenAI·전체 dev 선택; Codex가 API 실행 | 확인됨 |
| 최종 전체 F1에서 B가 높았다 | `results/experiment_results.json` → `automatic_evaluation.metrics.all.f1` | A 0.51559, B 0.72521; 차이 +20.9621%p; paired bootstrap 95% CI [+20.2093, +21.7153]%p; paired t-test JSON p=0.0(부동소수점 underflow) | Codex가 실행·채점; 해석은 아래 판단 장면 참고 | 확인됨 |
| 세그먼트별 abstention trade-off가 있다 | 동일 result JSON → answerable/unanswerable | 불가능 F1 A 31.51%, B 68.09%; 가능 false abstention A 0.54%, B 3.34% | Codex가 측정 | 확인됨 |
| 첫 채점은 A의 문장형 abstention을 놓쳤다 | 초기 실행 결과와 현행 `src/scoring.py`, 재계산 결과 | 불가능 split에서 A의 문장형 거부 1,873/5,945건(31.51%)을 초기 채점기가 0점 처리; 수정 후 전체 F1 효과 +35.60%p에서 +20.96%p로 변경 | 초기 실패와 규칙 수정·재채점은 Codex | 확인됨 |
| 작은 표본 power 추정과 30건 judge 비교가 완료됐다 | `results/sample_size_power.csv`, `results/judge_summary.json` | 사후 power n=10 18.5%, n=30 84.8%; 소표본 n=10 방향 일치 95.7%; judge pairwise 일치 21/30=70%, κ=0.366, Spearman ρ=0.704 | Codex가 실행·분석; 사용자는 결과를 아직 별도 채택하지 않음 | 확인됨 |
| 토큰 사용량 추정액이 $10 미만이다 | result JSON metadata; `src/llm.py` `CostBudget`; `results/budget_reservations.json` | 생성 5,192,784 input + 290,163 output token; judge 8,955 input + 420 output token; 표준 단가 적용 추정 $0.6655; 보수 예약 누계 $4.8201/$8 local cap | 사용자가 전체 데이터와 $10 ceiling 지정; Codex가 `gpt-6-luna`·예약 상한을 설정 | 일부—플랫폼 usage 화면의 실제 결제액은 확인하지 않음 |
| 키와 원본 데이터는 저장소에 포함되지 않는다 | `.gitignore`, `git check-ignore`, `data/squad_v2_dev.json` | `.env`, SQuAD 원본, JSONL 원시 출력, budget ledger는 ignore 대상 | Codex가 설정·검증; 키는 사용자가 로컬 `.env`에 입력 | 확인됨 |

## 판단 장면

### Dataset parser가 원본과 정규화된 `answers`를 다르게 표현했다

- 상태: 이번 작업에서 실제로 확인·수정
- 맥락: 공식 JSON의 `answers`는 `{text, answer_start}` 모양이지만 Hugging Face `datasets` JSON reader는 이를 answer record 목록으로 정규화했다.
- 첫 가설: 로더에서 원본 dict 모양만 읽으면 된다고 봤다.
- 대안: 원본 JSON을 직접 순회하거나 dict와 list 두 표현을 모두 받는다.
- 판단 기준: 지정된 `datasets` 기술을 유지하면서 실제 dev split을 손실 없이 읽는가.
- 실험: 전체 파일을 로드하고 데이터셋 통합 테스트에서 문항·세그먼트 수를 assertion했다.
- 관측: 첫 가정으로 테스트가 실패했다. 두 표현을 모두 지원하도록 수정 후 13개 테스트가 통과했고 11,873문항을 확인했다.
- 뜻밖의 결과: 라이브러리의 기능은 원본 JSON 구조와 같은 파이썬 타입을 보장하지 않았다.
- 결정: dict/list를 모두 파싱하도록 수정했다. Codex가 구현·시험했다.
- 한계: 임의의 SQuAD 변형을 지원한다고 확장 주장하지 않는다.

### 문장형 보류 응답을 채점기가 오답으로 오분류했다

- 상태: 실데이터 실행 결과를 검토해 수정하고 전체 재채점
- 맥락: 첫 점수기는 `NO_ANSWER`, `I don't know` 등 표준 짧은 표현 위주로만 abstention을 인식했다. Prompt A도 별도 지시 없이 자연어로 “The passage does not specify ...”라고 보류하는 문항이 있었다.
- 첫 가설: 규칙형 표현만 무응답으로 처리해도 비교가 공정하다고 가정했다.
- 대안: 문자열 전체를 빈 답으로 처리하거나, passage/context/text가 요청 정보를 제공·특정·언급하지 않는다는 명시적 거부 문장을 인식한다.
- 판단 기준: 사람이 읽었을 때 분명한 정보 부족 응답이 문장 형태 때문에 오답으로만 계산되지 않는가. 동시에 answerable 문항의 잘못된 거부를 false abstention으로 남기는가.
- 실험: 전체 prediction JSONL을 문항 ID에 따라 나누어 확인했다. `src/scoring.py`에 거부 표현 패턴을 추가하고 테스트 후 전체 experiment를 재실행했다. 재실행 로그는 A/B 응답 23,746건 cached, judge 30건 cached, pending 0이었다.
- 관측: 초기 전체 F1 차이는 +35.60%p, 초기 unanswerable A F1은 0%였다. 수정 후 A unanswerable 문장형 거부 1,873/5,945건을 반영했고 전체 F1은 A 51.56%, B 72.52%, 차이 +20.96%p로 바뀌었다. A unanswerable F1은 31.51%가 됐다. Answerable false abstention은 A 0.54%, B 3.34%로 나타났다. judge agreement도 초기 채점 기준 50%·κ=0.157에서 수정 채점 기준 70%·κ=0.366으로 달라졌다.
- 뜻밖의 결과: 채점 형식 차이 하나가 비교 효과를 14.60%p 바꾸고 judge 일치도까지 달리 보이게 했다.
- 결정: 표현이 자연어 문장이더라도 명시적으로 passage가 답을 제공하지 않는다고 하면 abstention으로 채점한다. answerable에서 같은 표현은 false abstention으로 표시하고 점수는 0으로 둔다. 구현·수정·재시험은 Codex가 했다.
- 한계: 이는 규칙 기반 구문 인식이지 사람 adjudication은 아니다. 규칙 추가에 따른 오탐은 향후 오류 표본 감사로 검토할 수 있다.

### 방향을 맞히는 소표본과 유의성을 검출하는 표본은 달랐다

- 상태: 전체 응답 및 judge 실험 뒤 새로 분석
- 맥락: 작은 샘플에서 B가 더 좋아 보이는 것과, 쌍체 검정이 차이를 유의하다고 검출하는 것은 별도 질문이다.
- 첫 가설: n=10에서 전체 데이터의 방향을 자주 맞히면 해당 규모도 충분한 비교 표본일 수 있다고 볼 여지가 있었다.
- 대안: 소표본 방향 일치율과 paired t-test 검정력을 각각 산출하고, judge pairwise tie 분포도 함께 확인한다.
- 판단 기준: 측정한 양(방향 재현 vs 유의성 검정력)을 분리해 주장하는가.
- 실험: 관측된 전체 F1 차이 0.2096을 기준으로 2,000회 복원 재표집해 표본 크기별 two-sided alpha=0.05 검정력을 계산했다. n=10 표본도 2,000회 추출해 방향 일치율을 계산했다. Judge는 answerable/unanswerable 각 15개로 구성했다.
- 관측: n=10 방향 일치율은 95.7%지만 검정력은 18.5%였다. n=30 검정력은 84.8%, n=50은 97.25%였다. Judge는 pairwise 21/30 일치, κ=0.366, Spearman ρ=0.704였고 30개 중 24개에서 두 후보 점수가 동점이었다.
- 뜻밖의 결과: 표본의 10개 질문만으로 B 방향을 자주 맞혀도, 유의성 검정력이 높다는 뜻은 아니었다. Judge 평균 점수는 B가 높았지만 다수의 tie가 선호 비교를 약하게 했다.
- 결정: n=10 방향 일치와 power 추정을 별도 결과로 보고한다. Judge 결과는 작은 same-model cross-check로만 서술하고 독립적 평가로 취급하지 않는다.
- 한계: power는 측정 후 관측효과를 고정한 사후 재표집이므로 새로운 환경에 대한 사전 보장치가 아니다. Judge 표본 30건도 작고 자동 채점과 같은 모델을 사용했다.

## 사용자 의사결정 지점

사용자는 OpenAI API와 SQuAD 전체 dev 실행, 지출 $10 이하를 선택했다. Codex는 현재 공식 공개 가격에 맞춰 `gpt-6-luna`를 택하고 로컬 비용 예약 가드를 $8로 뒀다. 사용자는 API 키를 채팅에 붙이지 않고 프로젝트 로컬 `.env`에 추가했다. OpenAI 프로젝트 spend limit 설정 여부는 확인되지 않았으며, 자동화는 각 요청의 보수 비용 예약으로 자체 차단한다.

## 실행·검증 상태

- API 생성: 23,746/23,746 answer completion, judge 30/30 완료; generation 실패 로그 0.
- API 호출 후 채점 수정 재실행: 23,746 generation cached, 30 judge cached, pending 0; 추가 API 요청 없이 집계만 재계산.
- 컨테이너 pytest: 13 passed.
- `docker compose config --quiet`: exit 0.
- `python3 -m py_compile src/*.py tests/*.py data/download.py`: exit 0.
- 토큰 usage 기반 표준 가격 적용 추정: $0.6655; 보수 예약 누계 $4.8201/$8 local cap. OpenAI billing dashboard와 결제 영수증은 확인하지 않았다.
- `.env`, 원본 SQuAD, prediction/judge JSONL, budget ledger는 Git ignore 대상이다. 집계 JSON/CSV는 재현 아티팩트로 제공한다.

## Claude가 이어서 할 일

1. 이 전달 메모와 `results/experiment_results.json`, `results/judge_summary.json`, `results/sample_size_power.csv`를 기준으로 GitHub README 및 Notion 사례를 정리한다.
2. 효과 크기 수정 원인을 숨기지 말고, 초기에 문장형 abstention을 놓친 채점기 가정과 이를 고친 후 결과가 어떻게 변했는지를 사고 과정으로 쓴다.
3. Judge 수치의 소표본·same-model·tie 경계와 power 수치의 사후 재표집 해석을 결과 가까이에 표시한다.
4. 루트 README·Notion 갱신 시 날짜·근거 없는 비용 및 성능 주장을 넣지 않는다.
