# WO-21 · 멀티모달 문서 key-value 추출 (multimodal document key-value extraction)

> 개인 프로젝트 · 대응 직군: AI 엔지니어 · 데이터: [FUNSD](https://guillaumejaume.github.io/FUNSD/), 원본 데이터는 로컬 다운로드

## 문제 정의

양식 문서에서 질문과 답변의 관계는 단어 뜻만으로 결정되지 않는다. 같은 OCR(Optical Character Recognition) 텍스트를 입력으로 두고, bounding box(경계 상자)에서 계산한 레이아웃(layout) 피처가 질문-답변 엔터티 연결(entity linking)에 얼마나 기여하는지 비교한다.

## 가설

- 질문-답변 단어를 연결한 텍스트 모델보다 텍스트와 상대 위치·거리·행 정렬·상자 크기를 함께 본 모델이 링크 F1을 높일 것이다.
- 좌표 근접 규칙은 가까운 표 셀을 빠르게 고를 수 있지만 반복되는 레이블과 복잡한 표에서는 학습 모델과 다른 실패를 보일 것이다.
- 남은 오답에는 인접 필드 혼동, 멀리 떨어진 값, 여러 줄 답변, 체크박스·기호처럼 텍스트 의미만으로 구분하기 어려운 사례가 포함될 수 있다.

## 접근 — 시도 순서

1. **공식 데이터와 분할 확인:** FUNSD 원본 archive를 내려받아 SHA-256을 확인하고 학습 149개·평가 50개 문서를 유지한다. 기존 OCR 텍스트·엔터티 라벨·좌표를 사용하므로 OCR 엔진 변경은 실험 변수에서 제외한다.
2. **텍스트 기준선:** 각 문서 내 모든 질문-답변 엔터티 조합을 후보로 만들고, 두 엔터티 텍스트의 TF-IDF(term frequency-inverse document frequency) unigram/bigram을 로지스틱 회귀(logistic regression)에 입력한다. 처음에는 0.5 고정 임계값을 사용했으나, 불균형 후보 집합에서 양성 링크를 지나치게 많이 예측했다.
3. **학습 문서 그룹 교차검증:** 같은 문서의 후보가 학습·검증에 나뉘지 않도록 5-fold 그룹 교차검증을 사용해 두 분류기의 F1 임계값을 학습 데이터에서 선택한다. TF-IDF 어휘도 각 fold 학습 문서에서만 fit한다. 분류기와 임계값을 포함한 전체 규칙은 테스트 평가 전에 고정한다.
4. **레이아웃 비교와 규칙 기준선:** 텍스트 피처에 정규화된 dx/dy, 중심 거리, 같은 행 여부, 수평 겹침, 상대 상자 너비·높이를 더한다. 별도의 거리 임계값 규칙도 학습 데이터에서만 정한다.
5. **정확한 링크 평가:** 정답 질문·답변 엔터티 후보는 양 모델에 동일하게 제공하고, `(문서, 질문 ID, 답변 ID)`의 정확한 연결을 micro entity-link F1로 계산한다. 문서 단위 paired bootstrap과 Wilcoxon signed-rank test(윌콕슨 부호순위 검정)로 쌍체 차이를 추정한다.
6. **오류 검토:** 평가 결과에서 거짓 양성 10개와 누락 링크 10개를 문서가 겹치지 않도록 고정 seed로 뽑아 원본 스캔 이미지에서 좌표를 직접 확인했다.

## 데이터

FUNSD의 공식 페이지는 199개 양식, 31,485개 단어, 9,707개 의미 엔터티, 5,304개 관계 및 학습 149/평가 50 분할을 안내한다. [공식 프로젝트 페이지](https://guillaumejaume.github.io/FUNSD/)의 2019년 논문을 출처로 둔다. 다운로드 archive SHA-256은 `c31735649e4f441bcbb4fd0f379574f7520b42286e80b01d80b445649d54761f`다.

**재현 중 발견한 집계 차이**: 내려받은 archive의 OCR 단어 레코드는 31,485개로 페이지와 일치하지만, `form` 레코드 직접 합계는 엔터티 9,743개였고 전체 directed relation 쌍은 5,294개였다. 공식 요약의 9,707/5,304와 차이가 있어 어느 쪽 숫자에도 맞춰 조정하지 않았다. 질문-답변 subset은 학습 3,129개, 평가 837개 링크다. 다운로드 스크립트는 archive checksum과 149/50 파일 수를 검증한다. 이 차이와 라이선스 메모는 [data/README.md](data/README.md)에 기록했다.

## 파이프라인

`data/download.py` archive 다운로드·checksum 및 split count 검증 → `src/dataset.py` JSON 엔터티·링크 파싱과 모든 질문-답변 후보 생성 → `src/features.py` 학습 전용 TF-IDF 및 정규화 좌표 피처 → `src/model.py` 5-fold 문서 그룹 교차검증으로 임계값을 선택한 로지스틱 회귀 → `src/rules.py` 좌표 근접 기준선 → `src/evaluation.py` exact link F1·paired bootstrap·Wilcoxon 및 오류 기록 → `results/experiment_results.json` 집계 결과.

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---|---|
| 텍스트 전용 key-value 링크 micro F1 | 공식 평가 분할에서 exact entity-link F1 | Precision 7.07%, Recall 39.67%, F1 **12.01%** |
| 텍스트+레이아웃 key-value 링크 micro F1 | 같은 문서·후보·분류기 설정 비교 | Precision 52.85%, Recall 76.46%, F1 **62.50%** |
| 레이아웃 추가로 인한 차이 | paired 차이, 문서 bootstrap 95% CI 및 유의성 | **+50.49%p**, 95% CI [+46.20, +55.13]%p; paired document Wilcoxon p = 1.42×10⁻¹⁴ |
| 좌표 거리 규칙 | 학습 split에서 cutoff 결정 후 평가 split | Precision 29.92%, Recall 46.36%, F1 **36.36%** |
| 실패 유형 분석 | 서로 다른 17개 문서에서 레이아웃 모델 오류 20건 시각 검토 | 거짓 양성 10건, 누락 링크 10건; 아래 실패 패턴 3종 기록 |
| 공식 분할 | 임의 재분할 금지 | train **149**개, test **50**개를 그대로 사용; 이 중 47개 test 문서에 질문·답변 후보 쌍이 있었고 3개는 답변 엔터티가 없어 후보가 0개 |

**측정 방식**: 테스트 split의 후보 21,727쌍과 정답 링크 837개에서 exact 엔터티 ID 관계를 집계했다. 문서별 F1 차이를 쌍체 비교하고 문서 단위로 2,000회 재표집했다. 모델에는 gold 엔터티가 후보로 주어지므로 이 수치는 OCR·엔터티 인식까지 포함한 end-to-end 점수가 아니라 entity-link F1이다.

## 시행착오와 의사결정

초기 0.5 임계값은 class-balanced 분류기에서도 테스트 후보 21,727개 중 텍스트 전용 7,871개, 레이아웃 모델 1,884개를 양성으로 예측했고 F1은 각각 10.75%, 56.67%였다. fold별 TF-IDF를 fit하는 문서 그룹 5-fold에서 임계값을 선택한 뒤 예측 수는 4,694개와 1,211개, 테스트 F1은 12.01%와 62.50%였다. 세 번째 기준선으로 학습에서 거리 cutoff를 고른 좌표 규칙은 36.36% F1을 냈다. 레이아웃 정보가 이 split에서 큰 이득을 줬지만, 낮은 텍스트 기준선과 테스트 문서 수를 함께 공개한다.

오류 20건을 직접 확인했을 때 남은 유형은 ① 표의 인접 열·행이나 반복 필드에서 가까운 잘못된 값을 고르는 경우, ② 질문과 답변이 멀리 떨어지거나 답변 상자가 여러 줄로 넓게 이어져 연결을 놓치는 경우, ③ 체크박스·짧은 숫자·기호처럼 단어 의미가 약해 좌표만으로 구분하기 어려운 경우였다. 테스트 전체에서는 텍스트 모델이 맞혔지만 레이아웃 모델이 틀린 506쌍(거짓 양성 418, 누락 88)도 확인했다.

## 측정 경계 (한계)

**다음 단계**: gold 엔터티 가정을 제거한 end-to-end 엔터티 추출과 실제 OCR 출력을 추가해 현재 링크 비교를 전체 문서 추출로 확장한다. 본 실험은 FUNSD에 포함된 OCR 텍스트를 그대로 사용했으므로 이미지 노이즈가 OCR 오류를 일으킨 비율은 측정하지 않았다. 공식 요약의 엔터티·관계 집계와 다운로드 archive의 직접 파싱 결과가 다르며, 공식 프로젝트 페이지에서 명시적인 데이터 재배포 라이선스를 확인하지 못했다. 원본 이미지와 상세 오류 레코드는 Git에 포함하지 않는다.

## 재현

프로젝트 폴더에서 실행한다. `data/raw/`와 `results/error*`는 Git에서 제외된다.

```bash
cd projects/wo-21-multimodal-document
docker compose run --build --rm download
docker compose run --build --rm test
docker compose run --build --rm experiment
```

## 개발 방식 (AI 활용 구분)

| 사용자가 제공·판단한 것 | Codex가 구현·검증한 것 |
|---|---|
| WO-21 프로젝트 질문, FUNSD 데이터셋과 149/50 분할 요구, Ship Gate | 원본 checksum 검증, 질문-답변 후보 파서, 텍스트·레이아웃 분류기, 좌표 규칙, bootstrap·Wilcoxon 분석, 시각 오류 표본 선정과 테스트 |

## 용어집

| 용어 | 뜻 |
|---|---|
| 경계 상자 (bounding box) | 문서 이미지에서 각 엔터티의 위치와 크기를 나타내는 좌표 네 값이다. 이 비교에서는 질문-답변의 상대 방향과 거리를 계산한다. |
| 그룹 교차검증 (grouped cross-validation) | 같은 문서의 후보가 학습과 검증에 나뉘지 않게 문서 ID 단위로 fold를 만든다. 테스트 split을 보지 않고 임계값을 정하는 데 쓴다. |
| 레이아웃 피처 (layout feature) | 엔터티 좌표에서 계산한 상대 거리, 방향, 같은 행 여부, 상자 크기 등을 뜻한다. |
| 로지스틱 회귀 (logistic regression) | 각 질문-답변 후보가 연결인지 분류하는 선형 모델이다. 텍스트 전용과 레이아웃 추가 모델에 같은 분류기를 적용했다. |
| 문서 단위 부트스트랩 (document-level bootstrap) | 문서들을 복원 추출해 성능 차이의 95% 구간을 계산한다. 한 문서의 후보쌍이 서로 독립이라는 가정을 피한다. |
| OCR 주석 (OCR annotation) | 원본 이미지를 OCR로 읽은 단어·좌표를 사람이 정리해 둔 FUNSD 입력이다. 이 프로젝트는 OCR 엔진을 다시 실행하지 않는다. |
| 엔터티 연결 (entity linking) | 질문 엔터티와 그 값을 담은 답변 엔터티를 key-value 관계로 연결하는 작업이다. |
| 엔터티 연결 F1 (entity-link F1) | 예측한 질문-답변 ID 쌍과 정답 ID 쌍의 precision·recall 조화평균이다. 단어 단위 F1이나 전체 문서 추출 성능과는 다른 측정값이다. |
| TF-IDF (term frequency-inverse document frequency) | 질문·답변 단어와 연속 단어쌍을 학습 문서 후보에서 가중치 벡터로 바꿔 텍스트 모델에 입력한다. |
| Wilcoxon 부호순위 검정 (Wilcoxon signed-rank test) | 같은 평가 문서에서 얻은 두 모델의 F1 차이가 0과 다른지 비모수 방식으로 비교한다. |

## English Technical Summary

WO-21 compares question-answer entity-link classifiers on the official FUNSD split: 149 training forms and 50 test forms. On 21,727 candidate links from 47 test forms with answer entities, the text-only TF-IDF model reached 12.01% micro link F1; adding normalized geometry features reached 62.50%, a paired gain of 50.49 percentage points (document-bootstrap 95% CI [46.20, 55.13], Wilcoxon p=1.42e-14). A distance-only rule reached 36.36% F1. Twenty visual error reviews found neighboring table fields, spatially displaced or multi-line answers, and symbolic values among remaining failure patterns. Three official test forms had no answer entities. The reported metric assumes gold entities and does not measure OCR or end-to-end extraction. The downloaded archive's direct entity/link counts differ slightly from the dataset overview and are recorded with its SHA-256.
