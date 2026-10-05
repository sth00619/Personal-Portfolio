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

각 프로젝트는 독립 완료가 아니라 이전 프로젝트의 한계에서 다음 가설이 출발하는 연결된 흐름입니다. WO-01의 검색 평가 하네스가 WO-02의 생성 품질 분리로 이어지고, WO-02에서 발견한 컨텍스트 선택 문제가 WO-03의 정책 설계 감각으로 이어지는 식입니다. WO-07~09는 광고·추천 도메인에서 같은 원칙을 반복합니다. WO-07의 확률 캘리브레이션이 WO-08의 입찰 전략 평가로 이어지고, WO-08에서 다룬 관측 지원 범위 문제가 WO-09의 반사실 평가(OPE) 설계로 이어집니다. WO-10~11은 인과추론과 조합최적화로 영역을 넓힙니다 — WO-10은 예상과 다른 결과(업리프트 모델이 기준선을 못 이김)를 숨기지 않고 보고하는 사례이고, WO-11은 공개 벤치마크로 구현을 먼저 검증한 뒤 시뮬레이션으로 확장하는 접근을 보여줍니다.

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

각 폴더 안의 `README.md`에 문제 정의·가설·시도 순서·결과·측정 경계·AI 활용 구분이 정리되어 있습니다.

---

## 실무 프레임워크 적응·검증 사례

| 프로젝트 | 검증 결과 | 초점 |
|---|---|---|
| [Sonamu 예제 환경 진단](./projects/sonamu-onboarding/) | 개발 DB 테이블 **21개** · 관리자 화면·Sonamu UI·API **3경로 HTTP 200** | 에이전트의 오류 가설을 실제 접속 대상과 실행 결과로 판정 |

공식 Miomock 예제의 로컬 실행을 바탕으로 호스트 PostgreSQL 포트 충돌을 진단하고, 예제 DB만 재매핑해 검증했다. 업스트림 구현과 별도로 작성한 것은 [포트 오버라이드](./projects/sonamu-onboarding/compose.port-override.yml), [점검 스크립트](./projects/sonamu-onboarding/scripts/smoke_miomock.py), [판단 기록](./projects/sonamu-onboarding/SESSION_REVIEW.md)이다.

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
│   ├── sonamu-onboarding/      # ✅ Sonamu 예제 환경 진단
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
