# WO-02 · 하이브리드 검색 기반 근거 인용 RAG

> 개인 프로젝트 · 대응 직군: AI 엔지니어 / 검색 ML  
> 데이터: BEIR SciFact (문서 5,183개 · 검색 300쿼리 · 생성 평가 30문제)  
> 브랜치: `dev/wo-02` · 커밋: `5c0804d7`  
> 외부 LLM API 미사용

## 문제 정의

BM25와 dense 검색을 결합하고 답변에 근거를 붙이는 RAG를 만들되, "인용이 붙었다"와 "올바른 근거를 인용했다"의 차이를 수치로 드러낸다. 그리고 검색 실패와 생성 실패를 분리해 다음 개선의 병목을 찾는다.

## 데이터

- BEIR SciFact: WO-01과 동일한 5,183개 문서 / 300개 검색 쿼리
- 생성 평가: 30개 질문 (calculation 10 / comparison 10 / lookup 10)
- 생성 평가 질문은 모두 정답 문서를 top 10 안에서 찾음 (retrieval failure 0)

## 접근 / 파이프라인

```
SciFact 문서 (128-token 청크)
  → BM25 + MiniLM dense (FAISS HNSW)
  → RRF Hybrid 융합
  → (선택) Cross-encoder reranking
  → 로컬 NLI 기반 SUPPORT/CONTRADICT 판정 + 근거 문장 추출
  → Citation coverage / correctness / faithfulness 분리 평가
```

## 결과 (Ship Gate 표)

### 검색 단계별 비교

| 단계 | Recall@10 | MRR | nDCG@10 |
|---|---:|---:|---:|
| BM25 | 0.7575 | 0.5942 | 0.6261 |
| Dense HNSW | 0.8015 | 0.6417 | 0.6728 |
| **Hybrid RRF** | **0.8244** | 0.6597 | **0.6905** |
| Hybrid + reranker | 0.8096 | **0.6605** | 0.6843 |

> **최고 설정: Hybrid RRF** — BM25 대비 Recall +6.69%p, nDCG +5.82%p  
> ⚠️ 리랭커 주의: RRF 단독보다 Recall -1.49%p, nDCG -0.62%p. MS MARCO 기반 모델이 SciFact 과학 도메인에 맞지 않음. MRR만 0.0008 상승.

### 생성 품질 (30개 답변)

| 지표 | 값 | 뜻 |
|---|---:|---|
| Citation coverage | 1.0000 | **모든** 답변에 인용 형식 존재 |
| Citation correctness | 0.8333 | 인용 문서가 정답 문서인 비율 |
| Extractive grounding | 1.0000 | 근거 문장이 인용 청크에 실제 존재 |
| **Composite faithfulness** | **0.5667** | 추출·정답 문서·올바른 판정을 **모두** 만족 |
| Answer relevance cosine | 0.6261 | 질문-답변 임베딩 유사도 |
| Verdict accuracy | 0.6333 | SUPPORT/CONTRADICT 정확도 |

> ⚠️ citation coverage 100%는 **인용 형식이 존재**한다는 뜻이며, 근거의 정확성을 보장하지 않습니다.

### 단계별 실패 집계

| 단계 | 실패 수 | 비율 |
|---|---:|---|
| Retrieval failure (top 10 미포함) | 53 / 300 | 17.7% |
| Generation failure (top 10에 있지만 답 실패) | 13 / 30 | 43.3% |
| Success (검색·판정 모두 성공) | 17 / 30 | 56.7% |

생성 실패 유형: calculation 4/10 · comparison 3/10 · lookup 6/10

### 인용 답변 예시

```
Claim: ALDH1 expression is associated with poorer prognosis in breast cancer.
Answer: SUPPORT. in a series of 577 breast carcinomas, expression of aldh1
detected by immunostaining correlated with poor prognosis. [45638119#c1]
→ Gold: SUPPORT ✓
```

## 시행착오와 해결

| 문제 | 원인 | 해결 |
|---|---|---|
| 다문서 NLI 과신 | 상위 5개 문서를 모두 NLI에 넣으면 비정답 문장 점수 과신 | 생성 컨텍스트를 **top 1 문서로 제한** |
| Top 1 제한의 trade-off | 정답이 2위 이하면 답변 기회 제거 | 새로운 실패 패턴으로 기록 (생성 실패 13건) |
| 리랭커 도메인 불일치 | MS MARCO 웹 검색 ≠ 과학 주장 검증 | RRF를 기본값으로 선택, 리랭커는 도메인 적합 모델 교체 후 재검증 |
| 단일 지표의 함정 | Citation coverage만 보면 품질 과대평가 | Coverage·correctness·faithfulness 분리 저장 |

## 한계

- 생성 평가 30개 — 통계적 유의성 검정 미시행
- Top 1 문서 제한으로 top 10 retrieval 성능을 생성에 충분히 활용하지 못함
- Faithfulness는 자동 복합 지표이며 사람 평가를 대체하지 않음
- 텍스트 초록만 사용 (논문 표·그림 정보 미포함)
- 다음 병목: 올바른 근거 선택 + 수치·부정·비교 관계 판정

## 개발 방식 (AI 활용 구분)

| 직접 작성 (SONG) | Codex 활용 |
|---|---|
| WO-01 설정 재사용·Ship Gate·검색/생성 실패 분리 기준 | BM25·FAISS·RRF·NLI 생성기·평가 코드 |
| 인용과 faithfulness를 별도 평가한다는 원칙 | 실패 분석, 테스트, Docker 환경 |
| 최종 기술 선택과 결과 해석 | 반복 실행, 아티팩트 생성, README 초안 |

코드는 테스트와 실제 300개 retrieval / 30개 generation 평가로 검증했습니다.

## 관련 개념

- **RRF**: 점수 척도가 다른 검색기를 rank 기반으로 안정적으로 융합
- **Extractive grounding**: 답변 근거 문장이 인용 청크에 실제로 있는지 검증
- **Retrieval failure vs Generation failure**: 다음 개선 우선순위를 결정하는 분리 지표

## English Technical Summary

Extended WO-01 into a full RAG pipeline. Combined BM25 and MiniLM dense retrieval (FAISS HNSW) with RRF, achieving Recall@10 0.8244 (+6.69 pp over BM25). Added a local-NLI-based extractive generator that cites source chunks for every answer. Evaluated 30 generation questions separately from 300 retrieval queries, separating citation coverage (1.00) from citation correctness (0.83) and composite faithfulness (0.57). Key finding: cross-encoder reranking using MS MARCO lowered Recall@10 and nDCG@10 versus RRF alone due to domain mismatch. Next bottleneck: context selection and NLI calibration for numeric/negation/comparison claims.
