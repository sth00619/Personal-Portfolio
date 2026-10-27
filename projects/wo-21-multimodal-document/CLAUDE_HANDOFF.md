# WO-21 전달 메모

## 근거 장부

| 주장 후보 | 코드·결과 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| 공식 FUNSD 분할을 보존했다 | `data/download.py`; archive SHA-256; `results/experiment_results.json` metadata | archive SHA `c31735649e4f441bcbb4fd0f379574f7520b42286e80b01d80b445649d54761f`; 149 train / 50 test annotations | WO-21이 dataset/split 지정; Codex가 다운로드·해시·split 검증 | 확인됨 |
| 텍스트에 레이아웃을 추가하면 이 구성의 링크 F1이 올랐다 | result JSON의 `text_only`, `text_plus_layout`, `paired_layout_delta` | 12.01% → 62.50%; +50.49%p; document bootstrap 95% CI [+46.20,+55.13]%p; paired document Wilcoxon p=1.42e-14 | WO-21이 비교 질문 지정; Codex가 실험·분석 | 확인됨 |
| 좌표 규칙은 learned layout model과 성능·실패가 다르다 | result JSON `coordinate_proximity_rule`; `src/rules.py` | 좌표 기준선 F1 36.36%, layout LogisticRegression F1 62.50% | 선택적 규칙 기준선은 Codex가 추가하고 시험 | 확인됨 |
| 공식 50개 중 3개 문서는 링크 후보를 만들 수 없었다 | `src/dataset.py`; local annotations; result metadata | 50 test docs 중 47개는 question+answer candidate가 있고, 3개는 question은 있으나 answer entity 0개. Train 149개 중 147개에 후보 pair가 있음 | Codex가 split 검증 중 발견; 공식 분할에서 제외하거나 재분할하지 않음 | 확인됨 |
| 평가 오류 유형을 시각 확인했다 | local `results/error_review_samples.jsonl` 및 `results/error_review.png` (Git 제외); `src/evaluation.py` | 고정 seed 21021로 거짓 양성 10, 누락 10, 17개 test 문서에서 직접 검토 | Codex가 표본 선정·이미지 좌표를 열어 검토 | 확인됨 |
| 데이터 수치와 공식 overview에 차이가 있다 | 공식 FUNSD overview와 archive 파서 통계; `data/README.md` | word records 31,485는 일치; form records 9,743 vs overview 9,707; distinct directed entity relations 5,294 vs overview relations 5,304; Q→A subset 3,966 (3,129 train / 837 test) | Codex가 출처 통계와 archive parse를 각각 기록 | 확인됨—집계 정의/아카이브 차이 원인은 미해결 |
| 문서 OCR 노이즈가 원인인 오류 유형을 측정했다 | 이 실험은 FUNSD 내 OCR text/boxes를 사용; Tesseract 등 재실행하지 않음 | OCR 원인별 오류율은 미측정 | WO-21이 OCR labels 활용을 지정; Codex가 모델 범위를 링크 예측으로 제한 | 근거 없음 |
| 데이터 재배포 라이선스를 확인했다 | 공식 프로젝트 페이지에는 데이터 overview와 2019 논문 인용만 있음 | 별도 dataset redistribution license를 공식 페이지에서 찾지 못함; 원본은 Git 제외 | Codex가 공식 페이지 검토 | 일부 |

## 판단 장면

### 후보 불균형에서 임계값 0.5는 맞지 않았다

- 상태: 이번 작업에서 실제 실행·수정
- 맥락: 문서 안의 모든 질문×답변 조합을 후보로 만들면 test 후보 21,727개 중 정답 링크는 837개(3.85%)였다.
- 첫 가설: class-balanced logistic regression의 기본 임계값 0.5로 비교해도 text-only와 text+layout의 차이를 볼 수 있을 것으로 예상했다.
- 대안: 0.5를 그대로 쓰거나 train documents만을 이용해 두 분류기의 cutoff를 각각 선택한다.
- 판단 기준: test label을 threshold tuning에 쓰지 않고 각 모델에 적정한 threshold를 적용하며, 한 문서 후보쌍이 CV train/validation으로 갈라지지 않도록 한다.
- 실험: 첫 0.5 pass에서 text-only는 7,871개, text+layout은 1,884개를 positive로 예측했다. 이후 `GroupKFold(5)`로 train document ID를 분리해 out-of-fold 점수에서 micro F1을 최대화하는 cutoff를 골랐다. 각 fold의 TF-IDF vocabulary는 그 fold train rows만으로 fit했고 최종 모델은 전체 train에서 재학습했다.
- 관측: threshold는 text-only 0.59368, text+layout 0.85514였다. Test positive 예측 수는 4,694개와 1,211개였고, F1은 12.01%와 62.50%였다. 학습 OOF F1은 9.15%와 62.07%였다.
- 뜻밖의 결과: class-balanced 로지스틱 회귀의 0.5 점수는 실제 3.85% positive 비율을 그대로 반영하지 않아 텍스트 기준선에 다수의 false positive를 만들었다.
- 결정: train 문서 그룹 CV에서 threshold를 정한 결과만 Ship Gate로 보고한다. 두 cutoff는 각각 결과 JSON에 남긴다.
- 한계: 후보 생성은 gold question/answer entities 전부의 cartesian product를 사용한다. 엔터티 검출 실수와 candidate pruning 성능은 이 수치에 포함되지 않는다.

### 공식 50개 평가 문서 중 3개에는 답변 후보가 없었다

- 상태: archive 파싱 중 새로 확인
- 맥락: 작업지시서는 공식 149/50 분할 유지와 50개 test 평가를 요구했지만, 3개 공식 test annotation은 question entities가 있으면서 answer entities는 하나도 없었다.
- 첫 가설: 50개 test annotation 모두 Q-A pair 후보를 포함한다고 가정했다.
- 대안: 해당 문서를 평가에서 숨기거나 split을 다시 나누는 대신 공식 분할 문서 수와 link 후보가 생성된 수를 따로 기록한다.
- 판단 기준: 문서를 재분할하거나 허위 zero-pair 행을 생성하지 않고 실제 링크 평가의 분모를 정확히 나타내는가.
- 실험: 모든 test annotation에서 question/answer label 개수를 확인하고 `load_split()` 후보 수와 대조했다.
- 관측: 50 test annotations 중 47개에서 21,727 Q×A candidates가 생성됐고, 3개 문서에는 answer entity가 0개였다. 837개의 gold links는 후보가 있는 split에서 평가됐다.
- 뜻밖의 결과: 작업지시서의 50개는 분할 문서 수로는 정확하지만 pair-link metric의 유효 문서 수는 47개다.
- 결정: 원래 50개 파일은 전부 보존하고, 결과에는 50 공식·47 candidate-bearing 문서를 각각 적는다.
- 한계: 이 3개 문서는 pair F1에 정보가 없으므로 document bootstrap은 실제 후보쌍이 있는 47개 문서를 단위로 한다.

### 좌표 피처는 가까운 표 셀과 멀리 떨어진 연결에서 서로 다르게 실패했다

- 상태: 최종 평가 후 새로 검토
- 맥락: layout model의 aggregate gain만으로 질문에서 어떤 구조 오류가 남는지 설명할 수 없었다.
- 첫 가설: 공간상 가까운 답변 후보가 많이 맞을 것이라 예상했지만 인접 필드가 오답이 되는 경우도 있을 수 있었다.
- 대안: 한두 개 눈에 띄는 예시만 뽑거나, seed를 고정해 FP 10건과 FN 10건을 test 문서 이미지에서 직접 확인한다.
- 판단 기준: 오류 쌍의 gold label, 두 모델 prediction, 원본 bbox 위치가 같은 문서 이미지와 일치하는가.
- 실험: seed 21021로 각 error class에서 문서별 사례를 하나씩 선택했다. 선택은 17개 문서에 퍼졌고 질문 상자/답변 상자를 색으로 표시해 원본 page를 열었다.
- 관측: 인접 열·행 또는 반복 field에서 가까운 다른 값을 선택하는 FP, 떨어져 있거나 여러 줄인 답변을 놓치는 FN, 체크박스·짧은 숫자·기호처럼 텍스트 유사도가 약한 사례를 확인했다. 전체 test에서는 text model은 맞고 layout model은 틀린 506쌍(418 FP, 88 FN)이 있었다. 별도 distance-only rule은 36.36% F1로 layout logistic model의 62.50%보다 낮았다.
- 뜻밖의 결과: 레이아웃은 이 split에서 평균 성능을 크게 끌어올리면서도 공간상 가까운 후보를 잘못 연결했고, 넓은 long-answer box 및 표 semantics를 해결하지 못했다.
- 결정: error sample 20건의 상세 텍스트와 이미지는 개인정보 가능성을 고려해 Git에 넣지 않고, 오류 유형별 요약과 집계만 공유한다.
- 한계: 20건은 정성 감사 표본이며 test errors 전체의 유형 비율로 일반화할 수 없다. OCR engine을 실행하지 않아 노이즈 원인을 OCR 측정치로 구분하지 않았다.

## 결과 해석 근거

- exact entity-link micro F1: `TP`는 같은 문서의 question ID와 answer ID 둘 다 맞은 링크, `FP`는 예측만 한 링크, `FN`은 누락 링크다. `F1 = 2TP / (2TP + FP + FN)`.
- 평가 후보: test의 47 candidate-bearing documents, 21,727 candidate pairs, 837 gold links.
- Text-only: TP 332, FP 4,362, FN 505; precision 7.07%, recall 39.67%, F1 12.01%.
- Text+layout: TP 640, FP 571, FN 197; precision 52.85%, recall 76.46%, F1 62.50%.
- Coordinate proximity rule: TP 388, FP 909, FN 449; precision 29.92%, recall 46.36%, F1 36.36%.
- Paired effect: micro F1 delta +50.4949 percentage points; paired document bootstrap 2,000 reps 95% CI [+46.2014,+55.1341]%p; Wilcoxon on per-document F1 differences p=1.4211e-14.
- Train-only grouped CV F1: text 9.15%, text+layout 62.07%, distance rule 30.40%. The two classifier thresholds use fold-local vocabularies and out-of-fold train scores; no threshold is tuned on test.
- `results/experiment_results.json` is committed. Full prediction/error case JSONL, sample image, dataset archive, and images remain ignored.

## 출처 및 측정 경계

- Dataset overview and paper citation: [FUNSD official page](https://guillaumejaume.github.io/FUNSD/), [FUNSD paper](https://arxiv.org/abs/1905.13538).
- 공식 페이지의 license notice를 찾지 못했다. 이 프로젝트는 raw dataset 및 error sample text를 커밋하지 않는다.
- 실험 대상은 question-answer link prediction이다. Entity recognition, OCR quality, image-quality degradation, LLM extraction은 모델 비교 범위 밖이다. Coordinate-only nearest-distance rule을 별도 비교했다.

## 실행·검증 상태

- Official archive download and SHA-256 verification: passed; train/test annotation counts 149/50.
- `docker compose run --build --rm test`: 5 passed.
- `docker compose run --build --rm experiment`: exit 0; result JSON and local error review records generated.
- `docker compose config --quiet`: pending final check.
- `python3 -m py_compile src/*.py tests/*.py data/download.py`: pending final check.
- `git check-ignore data/raw data/funsd.zip results/error_review.png results/error_review_samples.jsonl`: pending final check.

## 사용자 의사결정 지점

사용자는 WO-21 시작과 의미 있는 커밋 메시지 작성, 최종 결과를 `main`에 자동 커밋해 달라고 요청했다. 이 요청에 따라 프로젝트 구현은 작업지시서의 `dev/wo-21` 브랜치에서 진행한 뒤 로컬 `main`에 명시적인 merge commit으로 반영한다. 원격 push는 요청하지 않았다. 프로젝트 범위와 데이터셋은 WO-21 시작 파일에서 왔고, 모델·threshold·통계 및 오류 해석 선택은 Codex가 구현·측정했다.

## Claude가 이어서 할 일

1. 이 근거 장부, `README.md`, `results/experiment_results.json`을 바탕으로 GitHub/Notion 프로젝트 설명을 작성한다.
2. layout gain +50.49%p를 전체 문서 추출 성능으로 확대해 쓰지 말고, gold entity candidates를 전제로 한 entity-link F1이라고 결과 바로 옆에 쓴다.
3. 149/50 split, 50개 중 3개 answer-free test forms, archive count discrepancy와 license 확인 경계를 같이 기록한다.
4. 20건 오류 감사는 정성 표본이며, 분포 추정이나 OCR quality study로 과장하지 않는다.
