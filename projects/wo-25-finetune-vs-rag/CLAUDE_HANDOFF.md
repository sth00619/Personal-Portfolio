# WO-25 Claude handoff

> GitHub 루트 README와 기존 Notion WO-25 문서를 갱신할 때 이 근거 장부와 대표 판단 장면을 사용한다. README는 실측 결과와 재현 한계를 함께 적고, Notion에는 결과·사례를 읽기 쉬운 순서로 구성한다.

## 근거 장부

| 주장 | 근거 | 관측값 | 질문·구현·시험·결정 주체 | 상태 |
|---|---|---|---|---|
| 데이터 분리와 revision이 고정됐다 | `src/wo25/config.py`, `src/wo25/data.py`, `results/source_manifest.json` | GSM8K train 7,473; train에서 validation 200, train pool 7,273; 공식 test 1,319. revision 및 SHA-256 기록 | 사용자가 official train/test 분리를 요구; Codex가 다운로드·행 수·분할을 구현하고 확인 | 확인됨 |
| 네 GSM8K 방법이 같은 평가 조건을 쓴다 | `src/wo25/evaluate.py`, `src/wo25/scoring.py`, `results/gsm8k_summary.json` | 각각 1,319문항, 공통 4-bit base, greedy decoding, max 256 new tokens. zero-shot 702/1,319 (53.22%), few-shot 733/1,319 (55.57%), RAG 716/1,319 (54.28%), LoRA 620/1,319 (47.01%) | 사용자가 방법 비교를 요청; Codex가 파이프라인·채점 기준을 구현하고 실행 | 확인됨 |
| LoRA 선택은 고정 validation으로 했다 | `results/lora_sweep_runs.json`, `results/gsm8k_summary.json` | rank4/256: 95/200 (47.50%); rank4/1,024: 100/200 (50.00%), 선택; rank8/1,024: 99/200 (49.50%). 선택 설정으로 final 600 steps | Codex가 동일 validation sweep를 실행하고 최고 점수를 선택 | 확인됨 |
| few-shot/RAG 설정도 validation에서 골랐다 | `results/prompt_validation_sweeps.json` | few-shot 3: 135/200 (67.50%), 5: 121/200 (60.50%); RAG top-3: 117/200 (58.50%), top-5: 124/200 (62.00%) | Codex가 점수 기준으로 3-shot·top-5를 선택 | 확인됨 |
| LoRA 후 MMLU 표본 점수가 변했다 | `results/mmlu_summary.json`, `results/source_manifest.json` | 동일 100문항에서 base 52/100 (52.00%), LoRA 50/100 (50.00%), -2.00%p; 10개 과목에서 각 10문항 | Codex가 균형 표본을 고정하고 base·LoRA 평가 | 확인됨; 표본 일반화는 제한 |
| 대표 사례군이 세 종류 모두 최소 3건 확보됐다 | `results/gsm8k_analysis.json`, `results/interpretation.md` | 공통 오답 311건, RAG 단독 정답 52건, LoRA 단독 정답 42건; 원문 출력·검색 문항과 함께 각 3건 기록 | Codex가 전체 결과를 교차 집계하고 계산 과정을 검토 | 확인됨 |
| 테스트와 정적 구문 검사가 통과했다 | `tests/`, pytest, compileall | pytest 4 passed; `src`와 `tests` compileall 성공 | Codex가 로컬 프로젝트 환경에서 실행 | 확인됨 |

## 판단 장면

### 1. WO-16 코딩 모델을 재사용할지 수학 문제용 베이스를 정할지

- **상태:** 이번 작업에서 확인하고 실행한 판단.
- **맥락:** 네 방법에 동일한 베이스가 필요했고, 실행 장비는 Apple Silicon M4, 통합 메모리 16GB였다.
- **첫 가설:** WO-16의 Qwen Coder 3B를 재사용하면 검증된 MLX 실행 구성을 가져올 수 있다고 보았다.
- **대안:** 코딩 모델을 유지하거나, 수학 풀이용 instruction model을 선택해 같은 MLX 4-bit 경로로 변환할 수 있었다. 후자는 새 체크포인트 검증이 필요하지만 과제 적합성과 공개 조건을 다시 맞출 수 있었다.
- **판단 기준:** 수학 과제 적합성, 라이선스, 로컬 메모리, 동일 base 유지.
- **실험:** WO-16의 모델·라이선스·요구 패키지를 확인하고 MLX-LM 0.32.2 환경에서 Qwen2.5-1.5B-Instruct 고정 revision을 변환·로드했다.
- **관측:** WO-16 체크포인트는 코딩 특화 및 Research License였다. 새 Qwen 모델은 Apache-2.0, 변환된 4-bit 파일은 약 828 MiB였고 로컬 생성 smoke check를 통과했다.
- **뜻밖의 결과:** MLX-LM 변환 시 Hub repo ID와 로컬 캐시 revision 처리에서 저장 오류가 났다. 고정 revision을 먼저 내려받아 snapshot 경로를 변환기에 넘겨 해결했고, source manifest에 변환 모델 SHA-256과 quantization config를 기록했다.
- **결정:** 모든 비교 경로의 공통 베이스로 Qwen2.5-1.5B-Instruct 4-bit MLX를 사용했다.
- **한계:** 1.5B 모델 하나의 결과로 다른 크기·가속기 성능을 추론할 수 없다.
- **역할:** Codex가 라이선스·자원·목적을 확인하고 모델을 선택·변환했다.

### 2. 설정 선택과 최종 시험의 데이터 누수를 막는 방법

- **상태:** 분할, validation sweep, 공식 test 평가까지 완료.
- **맥락:** LoRA rank·학습 예제 수와 prompt 설정을 고르면서도 공식 test 결과는 독립적으로 보고해야 했다.
- **첫 가설:** 공식 test 일부로 빠르게 설정을 고를 수 있지만, 같은 문항을 선택과 최종 평가에 쓰게 된다.
- **대안:** 공식 train에서 고정 validation 200문항을 떼고 나머지 7,273개만 학습·검색에 쓰면 비교용 데이터는 줄지만 공식 test 전체를 보존할 수 있다.
- **판단 기준:** test 누수 차단, 재현 가능한 표본, 한 번에 하나의 실험 변수 변경.
- **실험:** seed 2507로 train에서 200개를 분리하고 index hash를 기록했다. rank4/256, rank4/1,024, rank8/1,024를 각각 100 steps로 비교하고, few-shot 3/5와 BM25 top-k 3/5도 같은 validation에서 측정했다.
- **관측:** LoRA는 95/200 (47.50%), 100/200 (50.00%), 99/200 (49.50%)였다. few-shot은 135/200 (67.50%) 대 121/200 (60.50%), RAG는 117/200 (58.50%) 대 124/200 (62.00%)였다.
- **뜻밖의 결과:** validation에서 선택된 LoRA rank4·1,024 설정은 공식 test에서 620/1,319 (47.01%)로 zero-shot 702/1,319 (53.22%)보다 낮았다. validation 우승이 test 우승을 보장하지 않았다.
- **결정:** rank4·1,024를 선택하고 final adapter를 600 steps 학습했으며, test 1,319개는 네 경로 평가에만 사용했다. few-shot은 3개, RAG는 top-5를 선택했다.
- **한계:** validation 200개·단일 split이므로 구성 간 작은 차이는 표본 변동일 수 있다. 반복 seed나 유의성 검정은 수행하지 않았다.
- **역할:** 사용자가 공식 train/test 분리를 요구했고 Codex가 split, sweep, 최종 평가를 구현·실행했다.

### 3. WO-02 하이브리드 검색 대신 BM25만 시험한 이유와 결과 읽기

- **상태:** 구현 및 전체 비교 완료.
- **맥락:** WO-02에는 BM25+FAISS 하이브리드가 있다. 이번 질문은 검색기의 조합 성능보다 prompting/RAG/LoRA 적용 경로를 비교하는 것이었다.
- **첫 가설:** 검증된 하이브리드를 모두 가져오면 RAG 성능을 높일 수 있다.
- **대안:** BM25만 쓰면 별도 임베딩 모델과 검색 변수를 추가하지 않아 방법 비교가 단순해지는 대신, 어휘가 다른 유사 문제를 찾지 못할 수 있다.
- **판단 기준:** 비교 변수의 통제, 기존 코드 재사용, 추가 모델·의존성 비용.
- **실험:** WO-02 BM25 경로를 확인하고 GSM8K train pool에서만 top-k를 검색했다. 현재 query와 같은 질문은 검색 후보에서 제외했다. validation에서 top-3와 top-5를 비교했다.
- **관측:** top-3는 117/200 (58.50%), top-5는 124/200 (62.00%)였다. 선택한 top-5의 공식 test 점수는 716/1,319 (54.28%)로 zero-shot보다 14문항 높고 few-shot보다 17문항 낮았다. RAG 단독 정답은 52개였다.
- **뜻밖의 결과:** 사례별 효과는 일정하지 않았다. case 76에서는 강아지 사료 예제 검색과 함께 RAG가 정답 5를 냈지만, case 74에서는 꽃·화분 어휘가 겹치는 예제 뒤에 정답 88을 냈다. 검색 사례와 답변 결과의 동시 관측만으로 검색이 정답 원인이라고 판단할 수 없다.
- **결정:** 이 비교의 RAG는 BM25 단독으로 유지하고, 하이브리드·dense retrieval 비교는 범위에 넣지 않았다.
- **한계:** 어휘 검색 하나와 단일 모델 결과이며, 검색 예제가 출력에 미친 인과 효과를 분리하지 않았다.
- **역할:** Codex가 기존 WO-02 구현을 확인하고 비교 목적에 맞춰 검색 구성을 결정했다.

## 핵심 결과 해석

- GSM8K에서 few-shot은 733/1,319 (55.57%)로 가장 높았다. zero-shot은 702/1,319 (53.22%), RAG는 716/1,319 (54.28%), LoRA는 620/1,319 (47.01%)였다.
- MMLU는 base 52/100에서 LoRA 50/100으로 -2.00%p 변했다. 100문항·10개 과목의 표본 결과이며, 일반 능력 전체의 저하로 단정하지 않는다.
- Exact match는 최종 숫자만 비교하므로 풀이 과정의 타당성까지 검증하지 않는다. 결과 해석은 이를 정확도 측정의 경계로 명시한다.
- 세 사례군 설명은 `results/interpretation.md`, 실제 출력과 retrieval ID는 `results/gsm8k_analysis.json`에 있다. 근거가 없는 실패 원인을 덧붙이지 않는다.

## Claude 전달 패키지

ZIP에는 소스 코드, 테스트, README, 핸드오프, 요청문, source manifest, sweep·score JSON과 대표 사례 해석을 포함한다. 원본·가공 benchmark 데이터, 변환 가중치, adapter와 전체 generation logs는 포함하지 않는다. GitHub 루트 README와 Notion은 아직 수정되지 않았고, `01_CLAUDE_REQUEST.md`에서 기존 페이지 갱신을 요청한다.
