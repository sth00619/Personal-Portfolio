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
4. **자동 채점:** SQuAD 정규화 기반 EM과 token F1을 계산한다. 첫 채점에서는 `NO_ANSWER`처럼 짧은 형식만 무응답으로 잡았으나, A가 `The passage does not specify ...`처럼 문장으로 보류한 응답을 틀린 답으로 분류하는 문제가 확인됐다. 해당 표현을 채점 규칙에 추가하고 저장된 답변을 다시 채점했다.
5. **통계 비교:** B−A 문항별 차이의 쌍체 t-검정과 paired bootstrap 95% 구간을 계산한다. 답변 가능/불가능 세그먼트의 F1 p-value에는 Holm 보정을 적용한다.
6. **소표본·judge 비교:** 문항별 F1 차이 재표집으로 크기별 사후 검정력을 추정한다. 30문항(각 세그먼트 15개)은 후보 순서를 섞어 LLM-as-judge 1~5점을 받고, 자동 F1과 winner 일치율·Cohen's kappa·Spearman 상관을 비교한다.
7. **비용 상한을 둔 전체 실행:** 사용자가 전체 dev를 선택했다. `gpt-6-luna` 실제 응답 usage로 산출한 토큰 비용 추정은 약 $0.67이며, 각 API 시도 전에 입력 byte 상한과 최대 출력 토큰을 예약해 로컬 누적 상한 $8에서 차단한다. 보수 예약 누계는 $4.82였다.

## 데이터

SQuAD 2.0 dev에는 **11,873문항**이 있고, 고정된 공식 파일에서 답변 가능 **5,928**, 답변 불가능 **5,945**를 확인했다. 답변 불가능 비중은 약 50%다. 원본 JSON은 다운로드 스크립트로 받으며 Git에서 제외한다.

공식 dev 파일은 4,370,528 bytes, SHA-256 `80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8`과 일치했다. 라이선스와 공식 evaluator는 [Stanford SQuAD 페이지](https://rajpurkar.github.io/SQuAD-explorer/)에서 확인할 수 있다.

## 파이프라인

`data/download.py` 공식 파일 다운로드·체크섬 검증 → `src/dataset.py` 문항 평탄화·표본 선택 → `src/prompts.py` 동일 질문용 A/B 프롬프트 → `src/llm.py` OpenAI Chat Completions 생성·judge와 요청 전 비용 예약 → 로컬 JSONL 체크포인트 → `src/scoring.py` EM/F1/abstention 채점 → `src/evaluation.py` 쌍체 검정·bootstrap·power → `results/` 집계 JSON/CSV.

API 키는 프로젝트의 로컬 `.env`에서만 읽으며 Git에 포함하지 않는다. 전체 dev 11,873문항에 답변 생성 23,746회와 judge 30회를 요청했다. 결과에 기록된 5,201,739 입력 토큰과 290,583 출력 토큰에 `gpt-6-luna` 표준 가격($0.10/백만 입력 토큰, $0.50/백만 출력 토큰)을 적용한 사용량 비용 추정은 $0.6655다. 각 호출 전 UTF-8 byte 수를 입력 토큰 상한으로 간주한 보수 예약 누계는 $4.82이며, 로컬 가드는 $8에서 새 요청을 막는다. OpenAI 사용량 화면의 청구 집계는 별도로 확인한다. 행 단위 답변과 예약 캐시는 로컬에만 저장된다.

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---|---|
| 전체 EM | paired 평균, B−A 95% bootstrap 구간 | A 37.83% → B 60.95%; +23.12%p [22.30, 23.91] |
| 전체 F1 | paired 평균, B−A 95% bootstrap 구간·t 검정 | A 51.56% → B 72.52%; +20.96%p [20.21, 21.72], p < 0.001 |
| Answerable F1 (n=5,928) | paired 비교, F1 Holm 보정 | A 71.67% → B 76.96%; +5.29%p [4.71, 5.86], Holm p = 4.88×10⁻⁷² |
| Unanswerable F1 (n=5,945) | paired 비교, F1 Holm 보정 | A 31.51% → B 68.09%; +36.59%p [35.32, 37.81], Holm p < 0.001 |
| Abstention / false abstention | 세그먼트별 A/B 비교 | Unanswerable: 31.51% → 68.09%; answerable false abstention: 0.54% → 3.34% |
| 자동 F1–LLM judge | 층화 표본 30건, 15/15 | judge 평균 A 3.83, B 4.63; pairwise 일치 21/30 (70%), κ=0.366, Spearman ρ=0.704 |
| 표본 크기별 검정력 | paired 재표집, 2,000회 | 사후 추정: n=10 18.5%, n=30 84.8%, n=50 97.25%; n=10에서 전체 방향 일치는 95.7% |

**측정 방식**: 공식 전체 dev에서 같은 모델·질문으로 A/B 응답 23,746건을 생성했다. p-value가 JSON에서 `0.0`으로 저장된 비교는 부동소수점 하한에 닿아 표에서 `p < 0.001`로 표시했다. 약 $0.67은 API 응답의 토큰 사용량과 현재 단가로 계산한 추정치이고, $4.82는 UTF-8 byte·최대 출력 길이를 예약한 보수 상한이다. Power와 소표본 방향 일치는 관측된 점수차이를 재표집한 사후 추정이다.

## 시행착오와 의사결정

두 종류의 시행착오가 결과 해석을 바꿨다. Hugging Face `datasets`가 `answers`를 원본 dict 대신 answer record 목록으로 정규화해 초기 로더 테스트가 실패했고, 두 형식을 모두 읽도록 수정했다. 이어 첫 채점에서는 A의 1,873개 문장형 보류 응답을 불가능 문항의 오답으로 세어 전체 F1 차이를 +35.60%p로 계산했다. 실제 응답과 judge 예시를 확인해 채점 규칙을 고치고 캐시를 다시 채점하자 차이는 +20.96%p로 수정됐다. 프롬프트 B는 여전히 높았지만, 효과 크기는 첫 채점 때보다 작았다. 현재 **13개 테스트 통과**.

## 측정 경계 (한계)

**다음 단계**: 사람 평가자 표본을 추가해 LLM judge의 tie 편향과 자동 점수 일치를 확인한다. judge 30건 중 두 응답 모두 5점을 받은 동점이 많았고 pairwise agreement는 70%, κ는 0.366이었다. 생성과 judge에 같은 모델을 사용했으므로 독립적 검증으로 보지 않는다. Power 수치는 관측된 결과 차이를 고정한 사후 재표집 추정이다.

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

WO-20 compares paired prompt variants on all 11,873 SQuAD 2.0 dev questions. Prompt B improved overall token F1 by 20.96 percentage points (95% paired bootstrap CI [20.21, 21.72]); its unanswerable F1 gain was 36.59 points, while answerable false abstention rose from 0.54% to 3.34%. An initial scoring pass missed 1,873 natural-language abstentions from prompt A; a revised refusal recognizer changed the estimated overall gain from 35.60 to 20.96 points. A 30-item same-model judge sample gave 70% pairwise agreement and κ=0.366, so this is a weak cross-check rather than an independent validation. Provider-reported token usage implies an estimated $0.67 at standard GPT-6 Luna rates; the conservative local request reservation was $4.82 under an $8 cap.
