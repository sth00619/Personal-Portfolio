# WO-17 Claude 전달 핸드오프

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| ESCI Task 1 small-version US test는 8,956개 query다 | Amazon Science 공식 README 표; `docs/source_manifest.json` | 공식 표: train 20,888 queries/419,653 pairs, test 8,956 queries/181,701 pairs | 사용자가 데이터셋·평가 목표를 지정; Codex가 출처 확인 | 확인됨 |
| Query 후보를 라벨이 있는 목록으로 제한해야 평가가 성립한다 | `data/README.md`, `src/pipeline.py`, 프로토콜 | 601,354 pair; 최대 188개 train, 95개 test 판정 후보; 미판정 전체 catalog 상품은 미포함 | 사용자 지침이 후보군 평가를 강조; Codex가 데이터 검증 후 범위를 고정 | 확인됨 |
| LTR이 hybrid RRF baseline보다 낫다 | `results/metrics.json`; 전체 공식 test 8,956 queries | Binary NDCG .6879→.7034; graded .7924→.8032; MRR도 두 기준에서 상승 | 사용자 비교 질문; Codex가 구현·측정 | 확인됨 |
| Binary·graded 평가의 개선 방향은 같고 크기는 다르다 | `results/metrics.json` | 두 기준 모두 NDCG/MRR 상승; binary NDCG +.0155, graded +.0109 | 사용자 비교 목표; Codex가 두 평가 기준 적용 | 확인됨 |
| 상위 5개 gain 피처가 hybrid 신호와 dense·lexical 구조를 반영한다 | `results/feature_importance.csv`, LightGBM gain importance | RRF 42.09%, dense rank 13.54%, dense cosine 12.02%, title overlap 11.09%, BM25 score 6.84% | 사용자 Ship Gate; Codex가 계산·주의사항 기록 | 확인됨 |
| 소스 원본의 무결성을 확인할 수 있다 | `data/download.py`, `docs/data_validation.md`; official Git LFS pointers | 예제 `4a735b693b4a424a6fc67f5be6e4c811495c488bbf66d02a602d308b2744263a`, 상품 `25124442d064d64b26f74082d6fa09438d679efc0c183cf28d19064a2b65a265`, pinned revision `7916cdf6ab75a462e77f20ab40428a10923998d5` | Codex가 LFS 설치 여부를 확인하고 검증 다운로드 구현 | 확인됨 |

## 판단 장면

### 1. 데이터 원본과 Python 환경의 재현 경계

- 상태: 이번에 새로 검증
- 맥락: 공식 ESCI 저장소의 대용량 Parquet이 Git LFS 파일이고 작업 머신에 `git-lfs`가 없었다.
- 첫 가설: 공식 저장소를 clone하면 원본 데이터를 재현 가능하게 가져올 수 있다고 예상했다.
- 대안: Git LFS 설치 후 clone하거나, pinned commit의 GitHub media URL에서 직접 스트리밍 다운로드할 수 있었다.
- 판단 기준: 저장소와 무관하게 프로젝트 스크립트 하나로 내려받고 원본 무결성을 확인할 수 있어야 했다.
- 실험: `git lfs version`, `git ls-remote`, 공식 raw LFS pointer 확인. 예제 파일 51,286,808 bytes, 상품 파일 1,108,857,465 bytes와 각각의 SHA-256 pointer를 확인했다.
- 관측: Git LFS 실행 파일이 없었지만 pinned revision `7916cdf6ab75a462e77f20ab40428a10923998d5`는 조회됐다.
- 뜻밖의 결과: 일반 `git clone`만으로는 작업 환경에서 원본 payload를 보장할 수 없었다.
- 결정: Python 표준 라이브러리 스트리밍 downloader를 구현하고 payload 크기·SHA-256으로 검증한다.
- 추가 관측: 기본 `python3`는 3.14.5였고 프로젝트 요구 버전은 3.11이다. 설치된 3.11.13으로 전용 `.venv`를 만들었다. CSV도 pinned revision의 SHA-256과 대조했다.
- 역할: 환경 확인, 다운로더 선택과 venv 격리는 Codex 판단.

### 2. 문서의 후보 상한과 실제 데이터 불일치

- 상태: 이번에 새로 검증
- 맥락: 작업지시서와 데이터 설명은 query당 최대 40개 judged products를 안내하지만, 전체 catalog의 미판정 상품은 relevance가 없다.
- 첫 가설: 공식 설명 및 작업지시서에 따라 query당 최대 40개 judged products일 것으로 예상했다.
- 대안: 전체 catalog retrieval을 평가하려면 미판정 제품의 relevance를 알아야 한다. 각 query의 labeled candidates 안에서 모든 주어진 후보를 순위화한다.
- 판단 기준: 미판정 상품을 비관련로 취급하는 평가 오류와 후보 recall을 순위 품질로 혼동하지 않을 것.
- 실험: 고정 revision의 `shopping_queries_dataset_examples.parquet`에서 `small_version=1`, `product_locale=us`를 필터하고 query_id별 row, unique product_id, split, label 수를 비교했다. 데이터 로더는 product table의 locale/id 키로 조인하고 누락 제목을 검사했다.
- 관측: train 20,888 query/419,653 pair; test 8,956 query/181,701 pair; 최대 candidate는 train query `airpods`의 188개, test split 95개였다. query당 product_id 중복은 없고 product join 누락도 없었다.
- 뜻밖의 결과: 안내된 40개 상한과 달리 실제 고정 데이터에 188개 후보 query가 있었다.
- 결정: 임의로 40개를 고르면 relevance 분포·평가 모집단이 바뀌므로 라벨이 있는 모든 후보를 보존하고 실제 최댓값을 보고한다. 전체 catalog 후보 발견은 평가하지 않는다.
- 한계: 결과는 판단이 존재하는 후보 안의 reranking 품질이며 전체 상품 검색 Recall이 아니다. Graded relevance E=3/S=2/C=1/I=0은 작업지시서가 정한 운영 라벨로, 공식 leaderboard와 직접 비교하지 않는다.
- 역할: 요구사항·가설은 사용자 지정. 공식 문서와 원본을 대조해 후보 상한의 차이를 확인하고 보존 정책을 택한 것은 Codex 판단.

### 3. LambdaMART 단일 설정과 평가 결과

- 상태: 이번에 새로 검증
- 맥락: 실험 질문은 일반화된 하이퍼파라미터 탐색이 아니라 동일 candidate split에서 RRF에 LTR을 더했을 때의 순위 변화다.
- 첫 가설: LambdaMART에 다수 설정을 튜닝하면 수치가 좋아질 수 있다.
- 대안: 고정된 단일 seed 구성으로 평가하거나, 별도 validation query split으로 튜닝한 뒤 한 번만 test를 평가할 수 있다.
- 판단 기준: 제공된 train/test 외부에서 test를 들여다보지 않고 단순 기준선을 비교한다.
- 실험: `src/pipeline.py`의 LGBMRanker 설정은 300 trees, learning_rate 0.05, num_leaves 31, min_child_samples 50, label_gain [0,1,3,7], seed 1707이다.
- 관측: 8,956 test queries에서 binary NDCG@10 .6879→.7034, MRR@10 .7773→.7923; graded NDCG@10 .7924→.8032, MRR@10 .9511→.9539. Top gain은 RRF score 42.09%, dense rank 13.54%, dense cosine 12.02%, title overlap 11.09%, BM25 score 6.84%였다.
- 뜻밖의 결과: 이진화와 graded 평가의 개선 방향은 같았다. 다만 binary NDCG 개선 +.0155가 graded +.0109보다 컸고 graded MRR 증가는 +.0028로 작았다. Binary만으로는 E/S/C 수준 차이의 개선 크기를 설명하지 못한다.
- 결정: validation 탐색 없이 사전 고정한 단일 구성을 실행한다. 더 넓은 hyperparameter search는 이 결과의 범위를 넘어 다음 단계로 둔다.
- 한계: 단일 seed·단일 parameter setting의 결과를 LambdaMART 전체의 상한으로 주장할 수 없다.
- 역할: 파라미터 범위와 튜닝 생략은 Codex 판단이며, 사용자 지정값이 아니다.

## 실행 결과

원본 측정은 Apple MPS에서 완료했다. `results/metrics.json`은 데이터·모델 revision/hash, 장치, 후보 규모, split·label 수와 전체 비교값을 보관한다.

- Hybrid RRF vs Hybrid+LambdaMART, binary: .6879/.7773 vs .7034/.7923.
- Hybrid RRF vs Hybrid+LambdaMART, graded: .7924/.9511 vs .8032/.9539.
- 두 relevance mode의 NDCG 및 MRR은 모두 개선; 방향 결론은 동일하고 크기는 다름.
- Train/test 규모: 20,888/8,956 queries, 419,653/181,701 pairs; 최대 후보 188/95.
- 상위 5 gain 중요도: RRF score 42.09%, dense rank 13.54%, dense cosine 12.02%, title overlap 11.09%, BM25 score 6.84%.
- 데이터 checksum·join 검증 완료. 오류나 누락 query-product joins 0건, query split overlap 0건.

## 사용자 결정 및 Claude 요청

- 사용자가 명시: WO-17 시작 요청 및 첨부 작업지시서의 증명 목표/데이터/Ship Gate.
- Codex가 판단: 고정 revision, Python 실행기 선택, dense embedding model, candidate-only 평가 경계와 feature 설정. 사용자가 직접 정한 수치 외에는 평가 결과를 바꾸지 않았다.
- Claude에 전달: 결과 README 및 근거 장부를 보고 GitHub/Notion 소개를 준비한다. 실행하지 않은 비교값·공식 benchmark와 다른 측정 경계를 과장하지 않는다.
