# WO-25 · 파인튜닝(Fine-tuning), 검색 증강 생성(RAG), 프롬프팅(prompting) 비교

> 개인 프로젝트 · 대응 직군: AI 엔지니어 / LLM 애플리케이션 · 데이터: GSM8K·MMLU (MIT)

WO-20은 같은 모델에서 프롬프트 버전을 비교했고, WO-25는 같은 베이스 모델에서 적용 방법(제로샷·퓨샷·RAG·LoRA)을 비교합니다.

## 문제 정의

수학 문장제에 언어 모델을 적용할 때 프롬프팅, 검색 증강 생성(RAG), 파인튜닝 중 무엇을 선택할지 실제 정확도와 실험 설정으로 판단할 근거가 필요합니다. 이 프로젝트는 모델·시험 문제·정답 추출 기준을 통제해 네 적용 방법을 비교합니다.

## 가설

- 유사한 풀이 예제를 검색해 문맥에 넣는 RAG는 별도 학습 없이 소량 예제로 이득을 얻을 수 있습니다.
- LoRA는 학습 예제와 계산량에 따라 프롬프팅보다 나을 수도, 아닐 수도 있습니다.
- 수학 풀이에 맞춘 LoRA가 일반 지식 선택형 문제(MMLU) 점수에 미치는 영향을 함께 측정합니다.

## 접근 — 시도 순서

1. Apple Silicon에서 실행 가능한 동일 베이스를 찾았습니다. WO-16의 Qwen Coder 3B를 그대로 쓰는 안은 수학 과제에 부적합하고 라이선스도 달라 제외했습니다. Apache-2.0 Qwen2.5-1.5B-Instruct를 고정 revision으로 선택해 4-bit MLX 양자화(quantization)를 적용합니다.
2. GSM8K 공식 train에서 200문제를 검증용으로 분리합니다. 이 검증 자료로 few-shot 수, RAG 검색 수, LoRA rank·학습 규모를 비교합니다. 공식 test 1,319문제는 최종 평가에만 씁니다.
3. 기준선은 제로샷(zero-shot), 고정 예제 퓨샷(few-shot), train 문제에서 BM25로 유사 풀이를 찾는 RAG입니다. LoRA는 같은 양자화 베이스에서 학습합니다.
4. 검증 결과로 LoRA 구성을 선택한 뒤 네 경로를 동일 GSM8K test 전체에서 채점합니다. 별도 MMLU 표본은 파인튜닝 전후 같은 문제·개발셋 예시로 비교합니다.

## 데이터

| 데이터 | 사용 범위 | 라이선스 | 고정 원본 |
|---|---|---|---|
| GSM8K | train 7,473, held-out validation 200, 공식 test 1,319 | MIT | [`openai/gsm8k`](https://huggingface.co/datasets/openai/gsm8k) |
| MMLU | 10개 과목에서 각 10개 test 문제, 과목별 dev 예시 | MIT | [`cais/mmlu`](https://huggingface.co/datasets/cais/mmlu) |
| 베이스 모델 | 네 GSM8K 경로의 공통 모델 | Apache-2.0 | [`Qwen/Qwen2.5-1.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) |

데이터셋과 모델 revision, 해시, 표본 수는 [`results/source_manifest.json`](results/source_manifest.json)에 남습니다. 내려받기는 [`data/README.md`](data/README.md)를 따르며 원본과 가공 데이터는 저장소에 포함하지 않습니다.

## 파이프라인

```text
고정 revision 데이터 → train / validation / 공식 test 분리
                                  ├─ zero-shot
                                  ├─ few-shot 예시
                                  ├─ BM25 검색 예시 → RAG
                                  └─ LoRA 학습 → adapter
          같은 GSM8K test 1,319건 → 숫자 정답 추출 → exact match
          MMLU test 100건, 같은 과목 dev 예시 → base / LoRA 비교
```

생성 원문과 문항별 정오 여부는 무시 경로 `artifacts/generations/`에 저장하고, 요약 JSON은 `results/`에 저장합니다. Docker는 이미 생성한 결과 파일의 채점·집계를 맡으며, MLX 추론과 학습은 Apple Silicon 호스트에서 실행합니다.

## 결과 (Ship Gate 표)

모든 GSM8K 비교는 고정된 Qwen2.5-1.5B-Instruct 4-bit 베이스와 그리디 디코딩(greedy decoding, max 256 new tokens)으로 공식 test 전체를 평가했습니다. LoRA 경로에만 최종 adapter를 적용했습니다. 정확도는 정답 수 ÷ 전체 수 × 100이며, 사례와 근거 해석은 [`results/interpretation.md`](results/interpretation.md), 문항별 생성 근거는 로컬 재현 산출물 `artifacts/generations/`에 있습니다.

| 지표 | 목표 | 실제 |
|---|---:|---:|
| GSM8K zero-shot | 공식 test 1,319문항 exact match | 702/1,319 (53.22%) |
| GSM8K few-shot (3-shot) | 공식 test 1,319문항 exact match | 733/1,319 (55.57%) |
| GSM8K BM25 RAG (top-5) | 공식 test 1,319문항 exact match | 716/1,319 (54.28%) |
| GSM8K LoRA (rank 4) | 공식 test 1,319문항 exact match | 620/1,319 (47.01%) |
| MMLU base → LoRA | 동일 100문항 정확도 및 %p 변화 | 52/100 (52.00%) → 50/100 (50.00%), -2.00%p |
| validation 설정 선택 | train에서 분리한 200문항 | LoRA rank4·256: 95/200; rank4·1,024: 100/200 (선택); rank8·1,024: 99/200 |
| prompt 설정 선택 | 동일 validation 200문항 | few-shot 3/5: 135/200·121/200 (3 선택); RAG top-k 3/5: 117/200·124/200 (5 선택) |
| 사례군 | 전체 방식 공통 오답·RAG 단독 정답·LoRA 단독 정답 | 311·52·42건; 대표 사례 각 3건 분석 |

정확도는 `정답 수 / 전체 문항 수 × 100`으로 계산합니다. MMLU 변화는 퍼센트 포인트(%p)로 표시합니다.

GSM8K 결과에서 few-shot은 zero-shot보다 31문항 높았고, RAG는 14문항 높았습니다. 선택된 LoRA adapter는 zero-shot보다 82문항 낮았습니다. MMLU 표본의 -2.00%p 변화는 100문항에 한정된 관측치입니다. 사례별 생성 출력과 해석 근거는 [`results/interpretation.md`](results/interpretation.md)와 [`results/gsm8k_analysis.json`](results/gsm8k_analysis.json)을 참조하세요. exact match는 숫자만 확인하므로 풀이가 틀려도 최종 숫자가 맞으면 정답으로 계산될 수 있습니다.

## 시행착오와 의사결정

- WO-16의 Qwen2.5-Coder-3B를 재사용할 수 있는지 검토했습니다. 코딩 특화 모델과 연구용 라이선스는 이 실험의 목적·공개 조건에 맞지 않아 제외했습니다.
- RAG는 별도 임베딩 모델을 추가하지 않고, 검증된 BM25 검색으로 GSM8K train의 풀이 예시를 가져오게 했습니다. 이로써 retrieval 변수가 검색 결과인지 추가 인코더인지 섞이지 않도록 했습니다.
- LoRA의 rank와 학습 예제 수를 한 번에 바꾸지 않도록 세 설정(4/256, 4/1024, 8/1024)을 비교하며 나머지 설정은 고정합니다. validation 결과 rank 4 / 1,024개를 선택해 final adapter를 600 steps 학습했습니다. 다른 두 설정은 각각 95/200(47.50%)과 99/200(49.50%)이었습니다. 3-shot(135/200, 67.50%)이 5-shot(121/200, 60.50%)보다 높았고, RAG top-5(124/200, 62.00%)가 top-3(117/200, 58.50%)보다 높아 각 설정을 선택했습니다. 세부 결과는 `results/lora_sweep_runs.json`과 `results/prompt_validation_sweeps.json`에 있습니다.

## 측정 경계 (한계)

- 1.5B 모델 한 개와 한 개의 4-bit 양자화·하드웨어 조합 결과라 대형 모델이나 GPU 서버에 일반화할 수 없습니다.
- MMLU는 10개 과목의 100개 표본이므로 광범위한 일반 능력을 대표하지 않습니다.
- BM25는 단어 겹침에 의존하는 어휘 검색입니다. 의미 기반 검색과의 비교는 포함하지 않습니다.
- 단일 학습 seed와 한 번의 생성 결과라 분산 및 통계적 유의성은 추정하지 않습니다.

## 개발 방식 (AI 활용 구분)

| 직접 작성한 것 | Codex가 생성한 것 |
|---|---|
| 비교 목적, 범위, Ship Gate 및 평가 질문 | 데이터 로더, 고정 분할·검색·학습·평가 파이프라인과 문서 초안 |
| 실행 환경과 허용 가능한 데이터·모델 출처 선택 | 단위 테스트와 재현 가능한 결과 저장 구조 |

## 용어집

| 용어 | 뜻 |
|---|---|
| GSM8K (Grade School Math 8K) | 풀이와 최종 숫자 답이 있는 초등 수학 문장제 벤치마크입니다. 공식 시험셋 전체를 최종 비교에 씁니다. |
| MMLU (Massive Multitask Language Understanding) | 여러 과목의 객관식 지식 벤치마크입니다. 여기서는 과목별 10문제 표본으로 LoRA 전후 변화를 봅니다. |
| BM25 (Best Matching 25) | 질문과 문서의 단어 빈도를 이용하는 어휘 검색 점수입니다. 이 실험에서는 학습 풀이를 고르는 RAG 검색기로 사용합니다. |
| MLX (Machine Learning for Apple Silicon) | Apple Silicon에서 모델 추론·학습을 수행하는 프레임워크입니다. 이 실험은 MLX-LM으로 4-bit 모델과 LoRA를 실행합니다. |
| 검색 증강 생성 (Retrieval-Augmented Generation, RAG) | 질문과 가까운 train 풀이 예제를 찾아 프롬프트에 넣는 방법으로, 이 프로젝트에서는 BM25가 예제를 검색합니다. |
| 제로샷 (Zero-shot prompting) | 예시 없이 문제와 지시만 전달하는 기준선입니다. |
| 퓨샷 (Few-shot prompting) | 고정된 몇 개의 풀이 예시를 질문과 함께 전달하는 방식입니다. |
| 파인튜닝 (Fine-tuning) | 학습 데이터로 모델 가중치를 추가 학습해 과제 수행 방식을 조정합니다. |
| 저랭크 적응 (Low-Rank Adaptation, LoRA) | 전체 가중치를 갱신하는 대신 작은 저랭크 어댑터를 학습하는 방법이며, 비교 대상 파인튜닝 경로입니다. |
| 양자화 (Quantization) | 모델 가중치의 표현 비트 수를 줄여 메모리 사용을 낮추며, 네 경로에서 같은 4-bit 베이스를 사용합니다. |
| 베이스 모델 (Base model) | 추가 학습이나 예제 검색을 적용하기 전의 공통 모델입니다. 비교의 네 경로가 같은 체크포인트를 공유합니다. |
| 정확 일치 (Exact match) | 추출한 최종 숫자를 정답 숫자와 비교하는 GSM8K 자동 채점 기준입니다. |
| 퍼센트 포인트 (Percentage point, %p) | 두 정확도 비율의 뺄셈으로 MMLU 전후 변화량을 나타내는 단위입니다. |
| 그리디 디코딩 (Greedy decoding) | 각 생성 단계에서 가장 높은 점수의 다음 토큰을 선택하는 방식입니다. 네 GSM8K 경로의 생성 변동을 줄이도록 고정했습니다. |
| 검증 분할 (Validation split) | 공식 train에서 따로 떼어 설정을 고르는 200문항입니다. 공식 test를 최종 평가에 남겨 두기 위해 사용했습니다. |
| 어댑터 (Adapter) | LoRA가 학습하는 작은 추가 가중치입니다. 파인튜닝 경로에만 적용하고 공통 베이스는 유지했습니다. |

## English Technical Summary

WO-25 compares zero-shot prompting, few-shot prompting, BM25-based retrieval-augmented generation, and LoRA adaptation on one pinned Qwen2.5-1.5B-Instruct base. It uses the official GSM8K test set (1,319 items) for final exact-match evaluation, a train-only validation split for configuration selection, and a balanced 100-item MMLU sample to measure general-knowledge change. On the full GSM8K test set, few-shot scored 733/1,319 (55.57%), BM25 RAG 716/1,319 (54.28%), zero-shot 702/1,319 (53.22%), and LoRA 620/1,319 (47.01%). On a balanced 100-item MMLU sample, accuracy changed from 52/100 to 50/100 (-2.00 percentage points). These results are limited to one small model, one seed, and the sampled MMLU subjects.
