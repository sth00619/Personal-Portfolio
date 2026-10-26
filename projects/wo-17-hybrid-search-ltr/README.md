# WO-17 · 하이브리드 상품 검색과 학습 순위화 (Hybrid Product Search and Learning to Rank)

> 개인 프로젝트 · 대응 직군: ML 엔지니어(검색) · 데이터: Amazon Science Shopping Queries Dataset 및 all-MiniLM-L6-v2, Apache-2.0

## 문제 정의

상품 검색에서는 검색어(query)와 상품 제목·설명·브랜드가 함께 쓰이고, 정답 라벨도 정확 일치(Exact), 대체품(Substitute), 보완재(Complement), 무관(Irrelevant)으로 나뉩니다. 키워드 순위와 임베딩 유사도를 결합한 하이브리드 검색(Hybrid Search)에 학습 순위화(Learning to Rank, LTR)를 더했을 때 순위 품질이 실제로 달라지는지 확인합니다.

## 가설

BM25(Best Matching 25)의 어휘 일치와 밀집 검색(Dense Retrieval)의 의미 유사도 순위를 Reciprocal Rank Fusion(RRF)으로 합치면 단일 신호보다 균형 잡힌 기준선을 얻을 수 있습니다. LightGBM LambdaMART는 이 점수에 브랜드 일치와 제목 겹침을 학습해 기준선보다 정규화 할인 누적 이득(Normalized Discounted Cumulative Gain, NDCG)@10을 높일 수 있습니다. Exact만 관련으로 보는 이진 평가와 ESCI 등급을 반영하는 graded 평가의 결론은 다를 수 있습니다.

## 접근 — 시도 순서

1. **평가 범위를 먼저 고정**: Amazon Task 1의 small_version 중 US 로케일(product locale)을 선택하고, 공식 학습/평가 검색어 분할(train/test query split)을 보존합니다. 검색어별 판정이 제공된 후보 목록 안에서만 순위를 매겨 라벨이 없는 상품을 정답 없는 오답으로 취급하지 않습니다.
2. **하이브리드 기준선 구성**: 각 쿼리의 후보 목록에서 BM25와 문장 임베딩 모델(Sentence Transformers)의 코사인 유사도를 각각 계산하고 RRF로 합칩니다.
3. **라벨 정의를 분리**: 이진 평가는 E만 양성으로 둡니다. graded 평가는 E=3, S=2, C=1, I=0을 사용하며, NDCG는 지수 이득(2^rel−1)과 로그 순위 감쇠로 계산합니다.
4. **LambdaMART 학습**: train query만 사용해 검색 점수, 각 순위, RRF, 브랜드 일치, 제목 토큰 겹침과 텍스트 길이를 학습합니다. test query는 모델 선택에 쓰지 않습니다.
5. **평가와 해석**: 같은 test 후보·라벨에 하이브리드 RRF와 RRF+LTR을 적용해 NDCG@10·평균 역순위(Mean Reciprocal Rank, MRR)@10을 이진/graded 기준으로 함께 비교하고, gain 기반 피처 중요도(feature importance)를 확인합니다.

## 데이터

[Amazon Science ESCI 저장소](https://github.com/amazon-science/esci-data)는 Task 1용 축소 버전에서 48,300개 query와 1,118,011개 query-product 판정을 제공합니다. 공식 표에서 US test는 8,956개 query와 181,701개 판정, train은 20,888개 query와 419,653개 판정입니다. 구현은 공식 US Task 1 small_version의 query 단위 split을 사용합니다.

예제 Parquet은 약 51 MB이고 상품 테이블은 약 1.1 GB입니다. 고정 revision 원본에서 US Task 1 small_version은 601,354 pair, 29,844 query이며 전체 split의 최대 후보 수는 188개(train), test split은 95개입니다. 공식 설명은 후보를 최대 40개로 소개하지만 실제 고정 파일의 train query `airpods`에는 188개, test query에는 최대 95개의 판정 행이 있어 라벨 행을 임의로 잘라내지 않고 모두 유지합니다. 수치와 후보 상한 차이는 [데이터 검증 기록](docs/data_validation.md)에 남겼습니다. 원본 파일은 저장소에 올리지 않으며 [고정 revision과 SHA-256 검증 다운로드 스크립트](data/README.md)를 제공합니다. Amazon Science 저장소와 [all-MiniLM-L6-v2 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)는 Apache License 2.0을 표시합니다. 데이터셋 논문은 [Shopping Queries Dataset 논문](https://arxiv.org/abs/2206.06588)을 인용합니다.

## 파이프라인

`공식 ESCI Task 1 데이터 → US small_version 필터 → query/product locale 키 조인 → 쿼리별 판정 후보 → BM25 + 임베딩 유사도 → RRF 순위 → LambdaMART 피처 학습 → 이진·graded NDCG@10/MRR@10 비교`

평가는 검색 후보 발견률(recall)이 아니라 라벨이 있는 쿼리별 후보 목록의 순위 품질을 측정합니다. 이 범위는 미판정 상품을 평가에서 제외하기 위한 선택입니다. binary MRR은 첫 E의 역순위, graded MRR은 첫 non-I의 역순위로 정의합니다. 둘 다 상위 10개에서 계산합니다.

## 실행

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python data/download.py
.venv/bin/python -m src.pipeline

# 대안: CPU 컨테이너에서 같은 파이프라인 실행
docker compose run --build --rm evaluate
```

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---:|---:|
| Hybrid RRF NDCG@10 / MRR@10 | binary, E만 관련 | 0.6879 / 0.7773 |
| Hybrid + LambdaMART NDCG@10 / MRR@10 | binary, E만 관련 | 0.7034 / 0.7923 (+0.0155 / +0.0150) |
| Hybrid RRF NDCG@10 / MRR@10 | graded E=3/S=2/C=1/I=0 | 0.7924 / 0.9511 |
| Hybrid + LambdaMART NDCG@10 / MRR@10 | graded E=3/S=2/C=1/I=0 | 0.8032 / 0.9539 (+0.0109 / +0.0028) |
| 평가 규모 | US Task 1 small_version | train 20,888 queries/419,653 pairs; test 8,956/181,701 |
| 후보 규모 | test 전체 query | 평균 20.29; p90 40; p95 40; p99 42; 최대 95 |
| 후보 상한 검증 | train/test 원본 | 최대 train 188, test 95; judged 후보 전부 사용 |
| LambdaMART 피처 중요도 | gain 상위 5개 | RRF 42.09%, dense rank 13.54%, dense cosine 12.02%, title overlap 11.09%, BM25 score 6.84% |

**측정 방식**: Sentence Transformers `all-MiniLM-L6-v2` 상품/검색어 임베딩을 Apple MPS에서 계산하고, 쿼리별 BM25와 RRF, train query에서 학습한 LightGBM LambdaMART를 공식 test 8,956개 query에 평가했습니다. MRR은 binary에서 첫 E, graded에서 첫 non-I의 상위 10 역순위입니다. 전체 지표·split·해시·모델 설정은 [결과 JSON](results/metrics.json), 상위 피처 표는 [CSV](results/feature_importance.csv)에 있습니다. Feature gain은 트리 분할의 상대적 기여 지표이지 인과 효과가 아닙니다.

Binary와 graded 모두 NDCG@10·MRR@10이 개선되어 모델 선택 결론은 같습니다. 개선 폭은 binary에서 NDCG +0.0155, MRR +0.0150이고 graded에서 각각 +0.0109, +0.0028입니다. 따라서 binary 평가는 개선 여부를 놓치지는 않았지만, S/C 등급 차이를 반영한 성능 크기와 순위 품질은 graded NDCG로 함께 설명해야 합니다. RRF score가 gain의 42.09%를 차지해 기준 하이브리드 순위가 LTR에서 가장 중요한 신호였고, 브랜드 일치 피처는 1.02%였습니다.

## 시행착오와 의사결정

- 데이터 파일이 Git LFS에 있어 기본 Git LFS 도구가 설치되지 않은 환경에서는 clone 방식이 곧바로 동작하지 않습니다. 공식 raw/Media URL에서 고정 revision의 파일을 직접 받고 LFS pointer에 명시된 크기와 SHA-256을 검증하는 다운로더를 만들었습니다.
- 기본 `python3`가 프로젝트 요구 Python 3.11이 아닌 버전일 수 있어 실행 환경을 명시적으로 확인했습니다. 이 프로젝트는 Python 3.11을 사용합니다.
- 작업지시서와 공식 데이터 설명은 query당 최대 40개 후보를 안내하지만, 고정 파일은 train query당 최대 188개, test query당 최대 95개 라벨 행을 포함합니다. 빈도와 라벨을 기준으로 잘라내면 평가대상이 바뀌므로 모든 judged candidate를 보존하고 split별 최대를 기록합니다.

## 측정 경계 (한계)

이 실험의 비교 범위는 benchmark가 판정한 후보를 대상으로 한 reranking 품질입니다. 전체 Amazon 카탈로그에서 후보를 새로 발견하는 retrieval recall, 온라인 전환, 사용자 만족도는 측정 범위에 포함되지 않습니다. **다음 단계**: 상품 카탈로그 전체 후보 생성 단계와 검색 효율을 별도 평가로 확장.

## 개발 방식 (AI 활용 구분)

| 직접 작성한 것 | Codex가 생성한 것 |
|---|---|
| WO-17 범위, 증명 목표, 데이터 범위와 Ship Gate | 다운로드 검증, 피처 파이프라인, LambdaMART 비교 코드 및 보고서 초안 |

## 용어집

| 용어 | 뜻 |
|---|---|
| 검색어 (Query) | ESCI에서 순위화 단위가 되는 사용자 검색 문구이며, 후보 상품과 관련도 판정이 이 검색어에 묶입니다. |
| 정확 일치 (Exact, E) | 검색어의 요구와 정확히 일치하는 상품 라벨이며 binary 측정의 유일한 양성입니다. |
| 대체품 (Substitute, S) | 사용자의 요구를 대체할 수 있는 상품 라벨이며 graded 측정에서 E 다음 relevance입니다. |
| 보완재 (Complement, C) | 검색 상품을 보완하는 관계의 상품 라벨이며 이 프로젝트 graded 척도에서 낮은 relevance를 받습니다. |
| 무관 (Irrelevant, I) | 검색 의도와 관련 없는 상품 라벨이며 binary·graded 평가 모두 relevance 0입니다. |
| 상품 검색 ESCI 벤치마크 (Exact, Substitute, Complement, Irrelevant) | 관련도를 네 라벨로 나눈 Amazon 공개 데이터셋입니다. |
| 하이브리드 검색 (Hybrid Search) | BM25 어휘 순위와 밀집 검색 의미 순위를 결합해 검색 신호를 보완하는 구성입니다. |
| 순위화 학습 (Learning to Rank, LTR) | 검색어별 상품 후보와 관련도 라벨로 더 좋은 순서를 학습하는 방식입니다. |
| BM25 (Best Matching 25) | 검색어 토큰이 상품 텍스트에 얼마나 잘 일치하는지 순위를 매기는 어휘 기반 검색 점수입니다. |
| 밀집 검색 (Dense Retrieval) | 검색어와 상품을 임베딩 벡터로 바꾸고 의미가 가까운 후보를 순위화합니다. |
| 코사인 유사도 (Cosine Similarity) | 검색어와 상품 임베딩의 방향 유사도이며, BM25와 단위가 달라 RRF로 결합합니다. |
| 순위 결합 (Reciprocal Rank Fusion, RRF) | 서로 단위가 다른 BM25·밀집 검색 점수를 직접 더하지 않고 순위 역수로 합쳐 기준선을 만듭니다. |
| 학습 순위화 트리 (LambdaMART) | 순위 지표를 최적화하도록 설계된 경사 부스팅 트리 방식으로, ESCI 등급 라벨을 학습합니다. |
| LightGBM | LambdaMART objective를 제공하는 gradient boosting 구현체이며, 이 프로젝트는 고정 train split에서 랭커로 학습했습니다. |
| 정규화 할인 누적 이득 (Normalized Discounted Cumulative Gain, NDCG) | 상위 순위의 관련 상품에 더 큰 가중치를 두며, 등급별 관련도를 반영하는 검색 품질 지표입니다. |
| 상품 로케일 (Product Locale) | 상품·검색어 국가/언어 구분 필드입니다. 이 프로젝트는 examples와 products 모두 `us` 값으로 제한합니다. |
| 문장 임베딩 모델 (Sentence Transformers) | 검색어와 상품 텍스트를 같은 벡터 공간에 표현해 의미 유사도를 계산하는 라이브러리입니다. |
| 평균 역순위 (Mean Reciprocal Rank, MRR) | 첫 관련 결과가 나타난 위치의 역수를 query 전체에서 평균한 지표입니다. 이 프로젝트는 상위 10개에 한정하고 관련도 정의를 명시합니다. |
| 이진 관련도 (Binary Relevance) | Exact만 관련(1)으로 두고 Substitute·Complement·Irrelevant를 비관련(0)으로 합쳐 평가하는 기준입니다. |
| 등급 관련도 (Graded Relevance) | Exact·Substitute·Complement·Irrelevant를 각각 3·2·1·0으로 유지해 NDCG에 반영하는 기준입니다. |
| 후보 재순위화 (Candidate Reranking) | 검색어별 후보 목록 안에서만 상품 순서를 바꾸는 단계이며 전체 카탈로그 recall과 구분합니다. |
| 경사 부스팅 결정 트리 (Gradient-Boosted Decision Tree, GBDT) | 여러 얕은 트리를 순차 결합해 예측하는 모델 계열입니다. LambdaMART가 이 계열의 학습을 순위 최적화에 적용합니다. |
| Metal Performance Shaders (MPS) | Apple Silicon에서 모델 연산에 사용하는 GPU 가속 백엔드이며, dense embedding 계산에 사용했습니다. |

## English Technical Summary

WO-17 compares BM25 and dense retrieval fused with Reciprocal Rank Fusion against a LightGBM LambdaMART reranker on Amazon Science's US Task 1 small-version ESCI split. On all 8,956 test queries, the reranker improves both NDCG@10 and MRR@10 under exact-only binary and graded ESCI relevance. The benchmark supplies judged query-product candidates, so the project ranks only those candidates and does not claim full-catalog retrieval recall. It reports gain-based feature importance and preserves query-level train/test separation.
