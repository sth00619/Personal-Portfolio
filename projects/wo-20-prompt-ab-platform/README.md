# WO-20 · 프롬프트 A/B 테스트 플랫폼

> 개인 프로젝트 · 대응 직군: AI 엔지니어, 데이터 사이언티스트 · 데이터: SQuAD 2.0 dev, [CC BY-SA 4.0](https://rajpurkar.github.io/SQuAD-explorer/)

> **WO-26과의 차이**: WO-26은 전환율 A/B 테스트의 통계 방법론을 다루고, WO-20은 같은 방법론을 LLM 응답 품질과 답변 불가능 질문의 abstention 비교에 적용한다.

## 문제 정의

프롬프트(prompt) A/B의 응답을 적은 예시만 보고 고르면 표본 크기와 평가 기준이 판단에 섞인다. 답변 가능·불가능 질문을 각각 평가하고, 같은 질문에 대한 응답 품질 차이를 쌍체 통계 검정과 효과 구간으로 확인하는 플랫폼을 만든다.

## 가설

- 답변 불가능할 때 `NO_ANSWER`를 요구하는 프롬프트 B는 해당 세그먼트에서 답변 보류(abstention) 탐지를 높일 수 있지만, 답변 가능 질문에서는 오답변 거부(false abstention)가 늘 수 있다.
- 전체 F1 평균 차이가 작아도 EM(Exact Match)과 answerable/unanswerable별 결과는 다른 결론을 낼 수 있다.
- 적은 예시의 무작위 표본은 전체 평가셋과 다른 우승 프롬프트를 보여줄 수 있다.

## 접근 — 시도 순서

1. **공식 원본 고정:** SQuAD 2.0의 공식 dev JSON을 내려받고 크기와 SHA-256을 확인한다. 데이터 로더는 Hugging Face `datasets`의 JSON 기능으로 읽어 문항 단위로 펼친다.
2. **쌍체 프롬프트 구성:** A는 지문에 근거해 간결히 답한다. B는 같은 입력과 출력 형식을 쓰고, 답이 지문에 없을 때만 `NO_ANSWER`를 내도록 지시를 추가한다.
3. **동일 질문·동일 모델 비교:** 같은 모델이 두 프롬프트로 각 질문에 답한다. 결과는 로컬 JSONL에 행 단위로 체크포인트해 중단 후 이어서 생성한다.
4. **자동 채점:** SQuAD 정규화 기반 EM과 token F1을 계산하고, 무응답 지시어를 빈 답으로 처리해 불가능 문항의 정확한 abstention을 별도 측정한다.
5. **통계 비교:** B−A 문항별 차이의 쌍체 t-검정과 paired bootstrap 95% 구간을 계산한다. 답변 가능/불가능 세그먼트의 F1 p-value에는 Holm 보정을 적용한다.
6. **소표본·judge 비교:** 문항별 F1 차이 재표집으로 크기별 사후 검정력을 추정한다. 30문항(각 세그먼트 15개)은 후보 순서를 섞어 LLM-as-judge 1~5점을 받고, 자동 F1과 winner 일치율·Cohen's kappa·Spearman 상관을 비교한다.
7. **비용 상한을 둔 전체 실행:** 사용자가 전체 dev를 요청했고, 현재 고용량 모델 `gpt-6-luna` 가격 기준 최악 상한 추정은 약 $4.48이다. 각 API 시도 전에 입력 byte 상한과 최대 출력 토큰을 예약해 로컬 누적 상한 $8에서 차단한다. 전용 API 프로젝트의 hard limit도 $8로 설정하는 전제를 둔다.

## 데이터

SQuAD 2.0 dev에는 **11,873문항**이 있고, 고정된 공식 파일에서 답변 가능 **5,928**, 답변 불가능 **5,945**를 확인했다. 답변 불가능 비중은 약 50%다. 원본 JSON은 다운로드 스크립트로 받으며 Git에서 제외한다.

공식 dev 파일은 4,370,528 bytes, SHA-256 `80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8`과 일치했다. 라이선스와 공식 evaluator는 [Stanford SQuAD 페이지](https://rajpurkar.github.io/SQuAD-explorer/)에서 확인할 수 있다.

## 파이프라인

`data/download.py` 공식 파일 다운로드·체크섬 검증 → `src/dataset.py` 문항 평탄화·표본 선택 → `src/prompts.py` 동일 질문용 A/B 프롬프트 → `src/llm.py` OpenAI Chat Completions 생성·judge와 요청 전 비용 예약 → 로컬 JSONL 체크포인트 → `src/scoring.py` EM/F1/abstention 채점 → `src/evaluation.py` 쌍체 검정·bootstrap·power → `results/` 집계 JSON/CSV.

API 키는 프로젝트의 로컬 `.env`에서만 읽으며 Git에 포함하지 않는다. 현재 실행은 전체 dev 11,873문항에 답변 생성 23,746회와 judge 30회를 요청한다. `gpt-6-luna` 표준 가격($0.10/백만 입력 토큰, $0.50/백만 출력 토큰) 기준으로 실제 provider token 사용량 비용을 결과에 기록하고, 각 호출 전 UTF-8 byte 수를 입력 토큰 상한으로 간주한 보수적 예약 비용은 로컬 $8에서 막는다. 전용 OpenAI API 프로젝트에 $8 hard limit을 두면 나머지 충전 잔액을 여유로 남긴다. 플랫폼 한도는 집계 반영이 즉시가 아닐 수 있으므로 예산 경보만으로 비용을 통제하지 않는다. 행 단위 답변과 예약 캐시는 로컬에만 저장된다.

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---|---|
| A vs B 전체 EM/F1 평균, B−A 95% 구간·paired t p-value | 같은 평가 문항, paired 비교 | 실행 대기 — 로컬 API 키 입력 필요 |
| Answerable / unanswerable EM·F1 및 p-value | 두 세그먼트 분리, F1 Holm 보정 | 실행 대기 — LLM 응답 생성 후 계산 |
| 불가능 질문 abstention 비율, 가능 질문 false-abstention 비율 | 세그먼트별 A/B 비교 | 실행 대기 — LLM 응답 생성 후 계산 |
| 자동 채점–LLM judge 일치 | judge 30건, 일치율·κ·ρ | 실행 대기 — 생성 및 judge 호출 필요 |
| 표본 크기별 검정력·소표본 방향 일치 | paired 재표집, 2,000회 | 실행 대기 — 전체 관측 F1 차이 필요 |

**측정 방식**: 데이터 행 수와 세그먼트는 로컬 검증했다. 약 $4.48은 모델 토큰 사용량 실측이 아닌 UTF-8 byte 상한·최대 응답 토큰 기반의 보수 추정이며, 실제 품질·비용·통계 결과는 API 실행 후 채운다.

## 시행착오와 의사결정

공식 JSON을 Hugging Face `datasets`로 처음 읽었을 때 `answers`가 원본의 딕셔너리가 아니라 answer record 목록으로 정규화되어 테스트가 실패했다. 두 구조를 모두 읽도록 로더를 고친 뒤 **10개 테스트가 통과**하고 전체 11,873문항·세그먼트 수를 재검증했다. 통계 결과와 사용자/에이전트 판단 장면은 [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md)에 갱신한다.

## 측정 경계 (한계)

**다음 단계**: 전용 API 프로젝트의 $8 hard spend limit을 확인하고 `.env`에 발급 키를 입력한 뒤 전체 응답 생성과 judge를 실행한다. 현재 비교 대상은 같은 기본 모델의 프롬프트 지시 변화이며, 모델 간 성능 비교는 아니다. LLM-as-judge는 자동 F1과 같은 모델이 선택될 수 있어 독립적인 사람 평가와 다를 수 있다. power 수치는 관측된 결과 차이를 고정한 사후 재표집 추정으로 보고한다.

## 재현

```bash
cd projects/wo-20-prompt-ab-platform
# .env.example에서 생성한 .env에 키를 추가하고 gpt-6-luna 전체 split 설정을 확인합니다.
${EDITOR:-nano} .env
docker compose run --build --rm download
docker compose run --build --rm test
docker compose run --build --rm experiment
```

현재 `.env`는 `LLM_PROVIDER=openai-compatible`, `LLM_MODEL=gpt-6-luna`, `JUDGE_MODEL=gpt-6-luna`, `SAMPLE_SIZE=0`, `COST_LIMIT_USD=8`로 준비되어 있다. `LLM_API_KEY=` 뒤에 프로젝트 키를 넣는다. 결과는 `results/experiment_results.json`, `results/judge_summary.json`, `results/sample_size_power.csv`에 저장된다.

## 개발 방식 (AI 활용 구분)

| 사용자가 제공·판단한 것 | Codex가 구현·검증한 것 |
|---|---|
| 프로젝트 정의·Ship Gate·SQuAD 데이터셋 지침 | 체크섬 다운로드, 데이터 검증, 프롬프트 실행기·채점·통계·judge 파이프라인 및 테스트 |

사용자는 OpenAI API와 전체 dev 실행, 총 $10을 넘기지 않는 범위를 선택했다. Codex는 현재 공개 가격과 전체 입력 크기로 `gpt-6-luna` 및 $8의 보수적 로컬 상한을 제안했다. 비밀 키는 사용자가 로컬 `.env`에만 추가하며, 전용 프로젝트 key와 spend limit을 별도로 설정해야 한다.

## 용어집

| 용어 | 뜻 |
|---|---|
| 프롬프트 (prompt) | 모델에 주는 시스템 지시문. A/B는 답변 불가 시 abstain 규칙을 바꾼다 |
| A/B 테스트 (A/B test) | 같은 평가 입력을 두 처리 버전에 적용해 결과 차이를 비교하는 실험 |
| EM (Exact Match) | 정규화한 모델 응답이 허용 정답과 완전히 같은지 측정하는 점수 |
| F1 (token F1 score) | 정답과 응답의 토큰 겹침을 precision·recall 조화평균으로 측정한다 |
| 무응답 (abstention) | 지문에 답이 없다고 보고 `NO_ANSWER`로 답변을 보류하는 행동이다. 불가능 질문의 올바른 탐지와 가능 질문의 불필요한 거부를 함께 평가한다. |
| 쌍체 t-검정 (paired t-test) | 같은 질문에서 얻은 A/B 점수 차이의 평균이 0과 다른지 검정한다 |
| 부트스트랩 (bootstrap) | 문항 쌍을 복원 추출해 평균 점수 차이의 불확실성 구간을 추정한다 |
| Holm 보정 (Holm correction) | 여러 세그먼트 가설을 검정할 때 가족 단위 거짓 양성률을 제어한다 |
| 검정력 (statistical power) | 실제 점수 차이가 있을 때 검정이 유의한 차이를 찾는 비율이다 |
| LLM-as-judge (LLM-as-a-judge) | 별도 언어 모델을 평가자처럼 사용해 응답 품질을 등급화하는 방식이다 |
| Cohen's kappa (Cohen's kappa) | 우연히 맞을 일치를 보정해 자동 평가와 judge의 범주형 선택 일치를 나타낸다 |
| Spearman 상관계수 (Spearman rank correlation) | 자동 점수와 judge 점수의 순위가 함께 변하는 정도를 나타낸다 |

## English Technical Summary

WO-20 compares two prompts on SQuAD 2.0 dev using paired exact match and token F1, answerable/unanswerable segments, and abstention rates. The verified official file contains 11,873 questions (5,928 answerable and 5,945 unanswerable). Prompt B adds an explicit `NO_ANSWER` rule when the passage does not support an answer. The pipeline includes paired t-tests, bootstrap intervals, Holm-corrected segment tests, post-hoc sample-size power estimates, and a blinded 30-item LLM judge sample. The official data and automated unit checks are verified; model quality and judge metrics remain pending a configured inference endpoint and model.
