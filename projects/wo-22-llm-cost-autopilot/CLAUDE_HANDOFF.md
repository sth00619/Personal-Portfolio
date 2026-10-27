# WO-22 Claude 전달 핸드오프

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| 두 정책 간 비교는 같은 SQuAD holdout과 저장된 응답을 사용한다 | `src/dataset.py`, `src/routing.py`, `results/experiment_results.json` | 전체 11,873; 문서 제목 그룹 train 8,915/26개, test 2,958/9개 | WO-22 지침이 SQuAD 재사용을 허용; Codex가 WO-20 trace 연결, split·검증 | 확인됨 |
| 라우팅은 비용을 줄이며 품질을 희생한다 | `src/experiment.py`의 `router.routed`, all-premium 비교 | F1 76.46% → 64.24%, −12.22%p; mixed price profile 비용 $1.71815 → $0.84116, −51.04%; paired question bootstrap 95% CI [−13.35, −11.04]%p | WO-22가 비용·품질 동시 평가를 요구; Codex가 임계값 .50과 평가 구현 | 확인됨 |
| 낮은 확률 문턱은 높은 절감과 큰 품질 손실을 만든다 | `results/experiment_results.json` `router.cutoff_curve`; `results/cost_quality_curve.svg` | cutoff .20: F1 53.75%, 비용 −93.50%; .95: F1 76.45%, 비용 −0.04% | Codex가 6개 cutoff 비교 | 확인됨 |
| 라우터 오분류 두 유형은 다른 결과를 만든다 | `src/experiment.py::_route_error_impact`, `router.errors` | hard→economy 851건, premium 대비 평균 F1 손실 43.70%p; easy→premium 478건, B 평균 F1 우위 −2.17%p | Codex가 학습 점수로 easy/hard 라벨을 만들고 test 오류 분리 | 확인됨 |
| semantic threshold는 train 기준을 통과하지만 holdout에서 안전하지 않다 | `src/semantic_cache.py`, `semantic_cache.calibration`, `semantic_cache.heldout_replay` | train precision 99.71%, cutoff .703; test top-1 precision 90.49%, 안전 기준 99.5% 미달; 280개 다른 질문 후보 오선택 | WO-03 precision gate 재사용 요청; Codex가 첫 평가 방식 수정 및 분리 test 측정 | 확인됨 |
| 캐시 절감은 오답 재사용 품질 저하를 동반한다 | `semantic_cache.heldout_replay`, 2-pass tiered cost fields | 통제 replay 2,958건에서 second-pass 비용 절감 49.86% ($0.83882); F1 64.24% → 59.78% (−4.46%p); false-hit 응답 F1 16.11% | Codex가 same-intent 변형·동일 문단 hard negative를 구성하고 점수화 | 확인됨 |
| 비용 절감 수치는 기존 두 프로젝트 단가 프로필에 의존한다 | `src/cost.py`, `metadata.price_profiles`, all-economy/all-premium 및 route metrics | WO-20 economy $0.10/$0.50 per million tokens, WO-18 premium $2/$8 per million; uniform premium 적용 시 router 비용 $1.72895로 all-premium $1.71815보다 약 0.63% 높음 | WO-22가 기존 가격을 새로 만들지 않고 재사용하도록 지시; Codex가 출처대로 프로필을 분리 적용 | 확인됨 |

## 판단 장면

### 1. 이미 생성한 WO-20 응답을 다시 쓸 것인가

- 상태: 이번에 새로 확인
- 맥락: 추가 API 비용 없이 품질 대리값과 입력/출력 token 수를 얻으려면 기존 답변 기록을 재사용할 수 있었다.
- 첫 가설: WO-20의 프롬프트 A/B 결과는 질문별 paired 출력이라 라우팅 정책 비교에 재사용할 수 있다고 판단했다.
- 대안: 새로운 저가·고가 모델을 호출하거나, 저장된 동일 모델 응답을 사용해 오프라인으로 정책만 비교할 수 있었다. 새로운 모델 호출은 비용과 결과의 재현 부담이 있고, 기존 기록은 모델 간 품질차를 증명하지 못한다.
- 판단 기준: API 호출과 비용을 추가하지 않고 동일 test 질문에서 비교 가능한 품질·token 사용량을 갖는가, 그리고 측정 경계를 정확히 드러낼 수 있는가.
- 실험: SQuAD 2.0 dev 11,873개 문항의 `results/predictions.jsonl`에서 A/B 각각 11,873개를 짝짓고, 문서 제목 단위 `GroupShuffleSplit`으로 train 8,915/test 2,958를 구성했다. 명령: `docker compose run --rm experiment`.
- 관측: test에서 all-premium B F1 76.46%, all-economy A F1 53.36%. A/B는 동일 GPT-6 Luna의 다른 프롬프트로 생성됐다.
- 뜻밖의 결과: 실제 모델 간 차이를 측정하지 않았고, WO-18 mock 가격과 WO-20 GPT-6 Luna 요율은 다른 금액·출처였다.
- 결정: 결과를 오프라인 정책 시뮬레이션으로 한정하고, 두 단가 출처를 서로 다른 rate profile로 보존했다. 사용자 지침이 기존 데이터/요율 재사용을 정했고 구현 선택은 Codex가 수행했다.
- 한계: 실 저가/고가 모델의 응답 품질 및 운영 청구액 비교가 아니다. 두 프로필이 서로 다르므로 비용 절감률은 프로필 가정에 민감하다.

### 2. 라우터의 경제 경로 진입 확률 문턱

- 상태: 이번에 새로 검증
- 맥락: 경제 경로 질문을 많이 보내면 절감이 커지지만 hard question도 저품질 답변에 노출된다.
- 첫 가설: 질문 텍스트의 TF-IDF로 프롬프트 A가 F1 0.80 이상을 낼 질문을 예측하면 운영 가능한 trade-off 곡선을 만들 수 있다.
- 대안: 보류 없이 모두 B로 보내거나, 확률 문턱을 낮춰 A 경로를 넓히거나, 높여 B 사용량을 유지할 수 있다.
- 판단 기준: 기사 제목 그룹 분리로 문맥 누출을 막고, test 기준을 최적화하지 않은 cutoff .50을 대표 정책으로 보고, 다른 다섯 cutoff를 곡선에 같이 둔다.
- 실험: train에서 A token F1 ≥.80 라벨로 TF-IDF + LogisticRegression 학습; test는 2,958문항. paired bootstrap 2,000회로 router와 all-premium의 질문별 F1 차이를 계산했다.
- 관측: .50에서 55.81%를 경제 경로로 보내고 혼합 비용 프로필 총액은 $1.71815에서 $0.84116으로 감소했다. F1은 76.46%에서 64.24%로 12.22%p 낮아졌다. 851 hard→economy 건의 평균 F1 차이는 −43.70%p였다. easy→premium 478건에서 프리미엄 B는 A 대비 평균 F1이 2.17%p 낮았다.
- 뜻밖의 결과: “easy” 학습 기준이 고비용 B가 항상 더 나은 품질을 뜻하지 않았다. 모델이나 프롬프트의 고비용 경로가 모든 세그먼트에서 품질 우위를 보장하지 않았다.
- 결정: test 성능이 최대가 되도록 cutoff를 조정하지 않고 .50 대표점과 전 cutoff 곡선을 함께 공개했다. 기본값·모델은 Codex가 구성했다.
- 한계: 분류기는 질문 텍스트만 보고, 저비용 적합 라벨은 기존 응답으로 만든다. production request distribution 또는 실 모델 fallback 결과는 아니다.

### 3. semantic cache의 threshold 선택과 holdout 실패

- 상태: 이번에 새로 검증
- 맥락: 비슷한 질문을 캐시에서 재사용하면 생성 비용을 줄이지만 다른 질문 답을 반환할 수 있다.
- 첫 가설: WO-03의 정밀도 기준 threshold를 같은 문단의 다른 질문 후보에 적용할 수 있다고 보았다.
- 대안: 모든 후보 pair를 단순 집계하거나, 실제 검색처럼 질의별 top-1 이웃만 threshold 판정하는 두 평가가 있었다. 첫 방식은 한 질의의 많은 오답 후보를 독립 hit로 계산해 검색 행동과 어긋났다.
- 판단 기준: exact cache가 먼저 잡을 질문 텍스트 동일 후보는 semantic 후보에서 제외하고, 동일 문맥 안에서 top-1 hit가 안전한지 평가한다. train precision ≥99.5%, true hit 최소 50개, +0.003 safety margin을 적용한다.
- 실험: 기사 그룹 train 8,915개로 동일 질문 prefix 변형과 같은 문단 hard negative를 만들고 word TF-IDF cosine cutoff를 선택했다. 고정한 threshold로 test 2,958개 재생 및 같은 문단 다른 질문 25,014개 후보를 검사했다.
- 관측: train cutoff .703 precision 99.71%(8,888 safe/26 false). test top-1 precision은 90.49%(2,664 safe/280 false)로 목표 미달. 재생 비용은 second pass에서 49.86% 줄었지만 F1이 64.24%에서 59.78%로 4.46%p 떨어졌다. 오선택된 cached 답의 평균 F1은 16.11%였다.
- 뜻밖의 결과: train에서 통과한 precision threshold가 분리 test에서 크게 일반화되지 않았다. 비용 절감만 읽으면 품질 실패가 가려질 수 있었다.
- 결정: test에 맞춰 threshold를 다시 선택하지 않고 기준 미달을 공개한다. 이 설정은 안전 배포 기준을 통과하지 못한 것으로 해석한다. 평가 로직 수정과 해석은 Codex가 수행했다.
- 한계: same-context synthetic replay에서 해당 문단 요청을 미리 채운 warm candidate pool을 가정했으며 production hit distribution이 아니다. 임베딩 계산 비용·실제 캐시 infra latency는 제외됐다.

## Claude가 업데이트할 때 주의할 점

1. README의 결과와 측정 방식 설명을 유지하고, 이 시뮬레이션을 distinct live-model 비교로 바꾸어 쓰지 않는다.
2. `49.86%` cache savings는 held-out precision gate 실패 및 F1 손실 `−4.46%p`와 같은 문맥에서 함께 표기한다. 안전한 배포 절감이라고 설명하지 않는다.
3. WO-18, WO-20의 서로 다른 단가 프로필을 기존 측정 출처대로 쓰고, 가격 절감 효과가 그 가정에 민감하다는 경계를 유지한다.
4. 라우터의 쉬움/어려움 오분류 건수, answerable/unanswerable 분할, 여섯 임계값 곡선을 요약에 반영한다.
5. GitHub README와 Notion 케이스 스터디에는 전역 문서 규칙의 원어 병기, 용어집 형식, 측정 경계 표현을 따른다. `CLAUDE.md`와 다른 WO 폴더를 수정하지 않는다.

## Ship Gate 전달 요약

- Router: test 2,958; all-premium F1 76.46%, EM 64.77%; route cutoff .50 F1 64.24%, EM 51.01%; 비용 프로필 $1.71815 → $0.84116 (−51.04%); F1 delta −12.22%p, paired bootstrap 95% CI [−13.35,−11.04]%p.
- Misclassification: hard→economy 851, mean F1 loss 43.70%p; easy→premium 478, B mean F1 advantage −2.17%p.
- Cache: train precision 99.71%, test top-1 precision 90.49% (gate fail); 280 false reuse events, wrong reuse mean F1 16.11%; two-pass modeled savings 49.86%, cache F1 delta −4.46%p.
- Cost-quality SVG: `results/cost_quality_curve.svg`; raw aggregate JSON: `results/experiment_results.json`.
- Validation: Docker Compose test suite 5 passed; full-split experiment completed; additional model API calls: zero.
- Non-versioned inputs: `data/squad_v2_dev.json`, `data/model_predictions.jsonl`. Raw dataset and generated responses are excluded from the repository.
