# Personal Portfolio · Song Tae-ho

> AI Engineering · Data Science · 검색 시스템 · 금융 데이터

**Notion 케이스 스터디** → [Portfolio Hub](https://app.notion.com/p/3df76d2e4c1c80b1b168db16c30a457d)  
**라이브 사이트** → [sth00619.github.io/Personal-Portfolio](https://sth00619.github.io/Personal-Portfolio/)

---

## 원칙

이 레포의 모든 프로젝트는 세 가지를 갖춰야 완료로 인정합니다.

1. **Eval** — 정량 지표 (Recall@10, false-hit rate, Gini, ECE, OPE 추정 오차 등)
2. **Number** — 실제 측정한 숫자
3. **Tradeoff** — 왜 이 설정을 골랐는지, 다음에 무엇을 검증할지 말로 설명 가능

각 프로젝트는 독립 완료가 아니라 이전 프로젝트의 한계에서 다음 가설이 출발하는 연결된 흐름입니다. WO-01의 검색 평가 하네스가 WO-02의 생성 품질 분리로 이어지고, WO-02에서 발견한 컨텍스트 선택 문제가 WO-03의 정책 설계 감각으로 이어지는 식입니다. WO-07~09는 광고·추천 도메인에서 같은 원칙을 반복합니다. WO-07의 확률 캘리브레이션이 WO-08의 입찰 전략 평가로 이어지고, WO-08에서 다룬 관측 지원 범위 문제가 WO-09의 반사실 평가(OPE) 설계로 이어집니다. WO-10~11은 인과추론과 조합최적화로 영역을 넓힙니다 — WO-10은 예상과 다른 결과(업리프트 모델이 기준선을 못 이김)를 숨기지 않고 보고하는 사례이고, WO-11은 공개 벤치마크로 구현을 먼저 검증한 뒤 시뮬레이션으로 확장하는 접근을 보여줍니다. WO-12는 검증 방식을 예측 문제로 확장합니다 — 분위수 예측 구간이 선언한 신뢰수준을 실제로 지키는지 분자·분모까지 재현하고, 가설과 반대로 나온 집계 레벨 결과도 그대로 보고합니다.

---

## WO 시리즈 — AI Engineering

| # | 프로젝트 | 핵심 결과 | 상태 |
|---|---|---|---|
| [WO-01](./projects/wo-01-retrieval-eval/) | 검색 평가 하네스 | Recall@10 **0.8244** · CI gate | ✅ |
| [WO-02](./projects/wo-02-hybrid-rag/) | 하이브리드 RAG | Hybrid RRF · Faithfulness 0.5667 | ✅ |
| [WO-03](./projects/wo-03-semantic-cache/) | 시맨틱 캐시 | False-hit 0/9 · 비용 67.5%↓(모델링) | ✅ |
| [WO-04](./projects/wo-04-multi-agent/) | 멀티워커 오케스트레이션 | 종료상태 30/30 일치 · 승인 전 지급 0건 | ✅ |
| [WO-05](./projects/wo-05-injection-guard/) | 프롬프트 인젝션 가드레일 | 공격 성공 60→0 · 오탐 2/100 | ✅ |
| [WO-06](./projects/wo-06-credit-scorecard/) | 신용평가 스코어카드 | Gini 0.3045/0.3055 · 재학습신호 0건 | ✅ |
| [WO-07](./projects/wo-07-ctr-calibration/) | 광고 CTR 캘리브레이션 | Criteo ECE 0.0094→0.0025, Avazu로 독립 검증 | ✅ |
| [WO-08](./projects/wo-08-rtb-bidding/) | RTB 입찰 전략 & 예산 페이싱 | 4개 전략 재생 · 관측 지원 범위 내 비교 | ✅ |
| [WO-09](./projects/wo-09-ope-recommender/) | 2단 추천 + 반사실 평가 | DR 실측 대비 오차 0.027%p | ✅ |
| [WO-10](./projects/wo-10-uplift-targeting/) | 프로모션 업리프트 타기팅 | Qini 6개 정책 비교, 반응 기준선이 우위(차이 95% 구간에 0 포함) | ✅ |
| [WO-11](./projects/wo-11-dispatch-vrptw/) | 배달 배차 OR 시뮬레이터 | Solomon gap 0.00~9.02% · MIP 배치 거리 7.92%↓ | ✅ |
| [WO-12](./projects/wo-12-demand-quantile-forecast/) | 수요 분위수 예측 | 누수 없는 28일 직접 예측, 품목 커버리지 86.82% vs 집계 58.33% | ✅ |

각 폴더 안의 `README.md`에 문제 정의·가설·시도 순서·결과·측정 경계·AI 활용 구분이 정리되어 있습니다.

---

## 실무 프레임워크 적응·검증 사례

| 프로젝트 | 검증 결과 | 초점 |
|---|---|---|
| [Sonamu 예제 환경 진단](./projects/sonamu-onboarding/) | 개발 DB 테이블 **21개** · 관리자 화면·Sonamu UI·API **3경로 HTTP 200** | 에이전트의 오류 가설을 실제 접속 대상과 실행 결과로 판정 |

공식 Miomock 예제의 로컬 실행을 바탕으로 호스트 PostgreSQL 포트 충돌을 진단하고, 예제 DB만 재매핑해 검증했다. 업스트림 구현과 별도로 작성한 것은 [포트 오버라이드](./projects/sonamu-onboarding/compose.port-override.yml), [점검 스크립트](./projects/sonamu-onboarding/scripts/smoke_miomock.py), [판단 기록](./projects/sonamu-onboarding/SESSION_REVIEW.md)이다.

---

## 다음 확장 — WO-25~28 (데이터셋 검증 완료, 착수 예정)

WO-01~12가 검색·추천·광고·인과추론·조합최적화·예측을 다뤘다면, 이 네 프로젝트는 세 방향으로 범위를 넓힙니다: **LLM 적용 방식의 비교**(파인튜닝 vs RAG vs 프롬프팅), **실험설계 방법론**(A/B 테스트의 통계적 함정), **제조 도메인**(설비 예지보전·생산 스케줄링 — 산업공학 전공과 직결). 네 프로젝트 모두 데이터셋 출처·라이선스·스키마를 미리 검증해뒀습니다.

| # | 프로젝트 | 핵심 질문 | 데이터셋 | 상태 |
|---|---|---|---|---|
| WO-25 | 파인튜닝 vs RAG vs 프롬프팅 비교 | 같은 과제·같은 베이스 모델에서 LoRA 파인튜닝이 RAG·프롬프팅보다 실제로 나은 지점은 어디인가 | GSM8K (MIT 라이선스, 자동 채점 가능) | ⬜ 데이터셋 검증 완료 |
| WO-26 | A/B 테스트 검정력·순차검정 프레임워크 | 사전 표본 크기 계산 없이 들여다보며 멈추면 거짓 양성률이 실제로 얼마나 높아지는가 | Marketing A/B Testing (Kaggle, CC0, 588,101행 실제 광고 로그) | ⬜ 데이터셋 검증 완료 |
| WO-27 | 제조 설비 예지보전 (RUL 예측) | 센서 시계열로 설비 잔존수명을 얼마나 정확히, 얼마나 일찍 예측할 수 있는가 | NASA C-MAPSS 터보팬 엔진 열화 시뮬레이션 (NASA PCoE 공식 공개) | ⬜ 데이터셋 검증 완료 |
| WO-28 | 제조 생산 스케줄링 최적화 | Job-shop 스케줄링에서 OR 솔버가 공개 벤치마크의 알려진 최적해를 얼마나 재현하는가 | OR-Library job-shop 벤치마크 (ft06/la01~40, 공식 최적해 포함) | ⬜ 데이터셋 검증 완료 |

각 프로젝트는 착수 시 WO-01~12와 동일한 구조(문제 정의 → 가설 → 접근 — 시도 순서 → Ship Gate → 측정 경계 → 용어집)로 작성됩니다.

---

## Data Profolio — 데이터 분석·엔지니어링

| # | 프로젝트 | 스택 | 상태 |
|---|---|---|---|
| P1 | 실시간 금융 거래 이상탐지 | XGBoost · Airflow · FastAPI · Redis | ⬜ |
| P2 | SaaS 고객 이탈 예측·코호트 | LightGBM · SHAP · dbt | ⬜ |
| P3 | 서울 대중교통 지연 예측 | PostGIS · LSTM · Mapbox | ⬜ |
| P4 | K-뷰티 글로벌 트렌드 | pytrends · Prophet · ES | ⬜ |
| P5 | 서울 상권 입지 추천 | H3 · PostGIS · Deck.gl | ⬜ |
| P6 | 글로벌 인텔리전스 플랫폼 | Mapbox Globe · Deck.gl | ⬜ |
| P7M | 그로스 마케팅 성과 분석 | GA4 · RFM · ROAS | ⬜ |
| P7P | SaaS 프로덕트 분석 | Aha Moment · RICE · dbt | ⬜ |

---

## 폴더 구조

```
Personal-Portfolio/
├── CLAUDE.md              # Codex 공통 규칙 + 문서화 지침
├── README.md              # 이 파일
├── projects/
│   ├── wo-01-retrieval-eval/   # ✅ 검색 평가 하네스
│   ├── wo-02-hybrid-rag/       # ✅ 하이브리드 RAG
│   ├── wo-03-semantic-cache/   # ✅ 시맨틱 캐시
│   ├── wo-04-multi-agent/      # ✅ 멀티워커 오케스트레이션
│   ├── wo-05-injection-guard/  # ✅ 프롬프트 인젝션 가드레일
│   ├── wo-06-credit-scorecard/ # ✅ 신용평가 스코어카드
│   ├── wo-07-ctr-calibration/  # ✅ 광고 CTR 캘리브레이션
│   ├── wo-08-rtb-bidding/      # ✅ RTB 입찰 전략 & 예산 페이싱
│   ├── wo-09-ope-recommender/  # ✅ 2단 추천 + 반사실 평가
│   ├── wo-10-uplift-targeting/ # ✅ 프로모션 업리프트 타기팅
│   ├── wo-11-dispatch-vrptw/   # ✅ 배달 배차 OR 시뮬레이터
│   ├── wo-12-demand-quantile-forecast/ # ✅ 수요 분위수 예측
│   ├── sonamu-onboarding/      # ✅ Sonamu 예제 환경 진단
│   ├── wo-25-finetune-vs-rag/  # ⬜ 파인튜닝 vs RAG vs 프롬프팅 (예정)
│   ├── wo-26-ab-testing-framework/  # ⬜ A/B 테스트 프레임워크 (예정)
│   ├── wo-27-predictive-maintenance/  # ⬜ 설비 예지보전 (예정)
│   ├── wo-28-job-shop-scheduling/  # ⬜ 생산 스케줄링 (예정)
│   └── ...
└── track-d-sql/           # SQL·DB 학습 기록
```

---

## AI 활용 방식

모든 프로젝트 README에 **AI 활용 구분** 섹션이 있습니다.

| 직접 작성 | Codex 활용 |
|---|---|
| 목표·제약·Ship Gate·기술 선택·시행착오 판단·결과 해석 | 보일러플레이트·Docker·스캐폴딩·반복 계산·테스트 코드 |

코드가 왜 그렇게 작동하는지 설명할 수 없는 부분은 사용하지 않았습니다.
