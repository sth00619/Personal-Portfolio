# WO-01 · 검색 평가 하네스 (Retrieval Evaluation Harness)

> 개인 프로젝트 · 대응 직군: AI 엔지니어 / 검색 ML  
> 데이터: BEIR SciFact test split (MIT 라이선스)  
> 브랜치: `dev/wo-01` · 커밋: `85fe4376`

## 문제 정의

RAG나 검색 시스템에서 "설정을 바꿨을 때 정말 좋아졌는가"를 의견이 아니라 숫자로 판단하고, 그 개선이 이후 변경에서 사라지지 않도록 CI로 방어한다. 평가 하네스가 없으면 모든 튜닝은 데모 수준에 머문다.

## 데이터

- BEIR SciFact test split: 문서 5,183개 · 판정 쿼리 300개 · 관련 문서 쌍 339개
- 고정 archive MD5 + 패키지 버전으로 재현성 보장
- 평가 단위: 문서 (청크 순위 → 부모 문서별 최고 점수로 복원)

## 접근 / 파이프라인

```
SciFact 문서
  → 청크 분할 (128 / 240 token, overlap 24)
  → BM25 인덱스 + MiniLM dense 임베딩 (FAISS)
  → RRF Hybrid 융합 (α 고정)
  → (선택) Cross-encoder reranking
  → Recall@10 / MRR / nDCG@10 · 카테고리별 분해
  → CI 회귀 게이트 (pytest)
```

## 결과 (Ship Gate 표)

### 설정별 비교

| 설정 | Recall@10 | MRR | nDCG@10 |
|---|---:|---:|---:|
| BM25 · 128 | 0.7575 | 0.5942 | 0.6261 |
| Dense · 128 | 0.8082 | 0.6448 | 0.6767 |
| **Hybrid · 128** | **0.8244** | **0.6647** | **0.6942** |
| Hybrid · 240 | 0.8138 | 0.6567 | 0.6849 |
| Hybrid · 128 + rerank | 0.8323 | 0.6635 | 0.6946 |

> 선택 설정: **Hybrid-128** (RRF). 리랭커는 Recall을 0.8323으로 올리지만 MRR이 소폭 하락하고 45.96초가 추가되어 기본 경로에서 제외.

### 카테고리별 (Hybrid-128 기준)

| 카테고리 | n | Recall@10 | MRR | nDCG@10 |
|---|---:|---:|---:|---:|
| negation | 30 | 0.8500 | 0.6797 | 0.7153 |
| numeric_or_comparative | 78 | 0.8165 | 0.6979 | 0.7092 |
| other | 192 | 0.8237 | 0.6488 | 0.6849 |
| **전체** | **300** | **0.8244** | **0.6647** | **0.6942** |

### CI 회귀 게이트

```bash
# 정상 후보
$ pytest -q tests
7 passed in 2.57s

# 의도적으로 낮춘 후보 (Recall@10 = 0.8000)
$ WO01_CANDIDATE=tests/fixtures/bad_candidate.json pytest -q tests/test_regression.py
AssertionError: Recall@10 regression: 0.8000 < 0.8144
1 failed in 0.01s  # exit code 1
```

Baseline 0.8244 · 최소 허용 0.8144 (1%p 허용)

## 시행착오와 해결

| 문제 | 원인 | 해결 |
|---|---|---|
| 512-token 청크가 모델 한도 초과 | MiniLM 최대 256 wordpiece | 128/240 token으로 변경, 초과 입력 거부 |
| 청크 단위 평가가 문서 qrels와 불일치 | 평가 단위 불일치 | 부모 문서별 최고 청크 점수 사용 후 중복 제거 |
| 리랭커가 모든 지표를 개선하지 않음 | MS MARCO vs SciFact 도메인 차이 | 지표별 trade-off 측정 후 기본 경로에서 제외 |
| 카테고리별 분석이 어려움 | SciFact 공식 카테고리 없음 | 상호 배타적 휴리스틱 카테고리 직접 정의 (표본 수 공개) |

## 실패 사례 대표 5개

| 유형 | 설명 |
|---|---|
| RRF 밀어냄 | BM25가 무관한 문서를 올려 유용한 dense 결과가 10위 밖으로 |
| 부정·주장 방향 | "~하지 않는다"처럼 부정 표현을 검색기가 구분 못 함 |
| 표현 불일치 | 짧은 주장 vs 긴 종합 논문의 어휘 간극 |
| 약어 오타 | `PPR` vs `PRR` 같은 약어·오타 차이 |
| 숫자 토큰 과적중 | 숫자가 무관한 문서를 과도하게 끌어올림 |

## 한계

- 카테고리는 공식 라벨이 아닌 휴리스틱 (표본 수와 함께 보고)
- SciFact 300 쿼리는 작아 통계적 유의성 검정 미시행
- 일반 영어 MiniLM / MS MARCO 리랭커 — 과학·의생명 특화 모델 아님
- 지연시간은 warm cache 조건 (초기 임베딩 생성 제외)
- **이 프로젝트는 retrieval만 평가** — 생성 품질은 WO-02에서 별도 측정

## 개발 방식 (AI 활용 구분)

| 직접 작성 (SONG) | Codex 활용 |
|---|---|
| 프로젝트 목표·Ship Gate·결과 해석 기준 | 검색기·평가기·CI 게이트 코드 |
| 검색과 생성 분리, 숫자로 판단하는 원칙 | 실험 실행, 테스트, Docker 환경 |
| 최종 설정 선택 및 트레이드오프 판단 | 반복 계산, 결과 파일 생성, README 초안 |

코드와 문서 초안에 AI를 활용했으며, 수치는 실제 실행 결과 JSON과 테스트 로그로 검증했습니다.

## 관련 개념

- **Recall@10 / MRR / nDCG@10**: 서로 다른 순위 특성을 측정 — 셋을 함께 봐야 의사결정이 왜곡되지 않음
- **RRF (Reciprocal Rank Fusion)**: 점수 분포가 다른 sparse/dense 검색기를 rank 기반으로 융합
- **CI 회귀 게이트**: "테스트의 존재"보다 "실패 조건을 재현한 로그"가 운영 신뢰성을 증명

## English Technical Summary

Built a retrieval evaluation harness on BEIR SciFact (5,183 docs, 300 queries). Compared BM25, dense (MiniLM + FAISS), Hybrid RRF, and cross-encoder reranking across Recall@10, MRR, and nDCG@10 with query-category breakdowns (negation, numeric/comparative, other). Hybrid RRF (chunk 128) achieved Recall@10 0.8244 and nDCG@10 0.6942, outperforming BM25 by 6.69 pp. Implemented a pytest CI gate that blocks PRs when Recall@10 drops more than 1 pp below baseline — demonstrated both passing and intentional failure (exit code 1).
