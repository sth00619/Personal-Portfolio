# Personal Portfolio · Song Tae-ho

> AI Engineering · Data Science · 검색 시스템 · 금융 데이터

**Notion 케이스 스터디** → [Portfolio Hub](https://app.notion.com/p/3df76d2e4c1c80b1b168db16c30a457d)  
**라이브 사이트** → [sth00619.github.io/Personal-Portfolio](https://sth00619.github.io/Personal-Portfolio/)

---

## 원칙

이 레포의 모든 프로젝트는 세 가지를 갖춰야 완료로 인정합니다.

1. **Eval** — 정량 지표 (Recall@10, false-hit rate, Gini, 종료 상태 일치율 등)
2. **Number** — 실제 측정한 숫자
3. **Tradeoff** — 왜 이 설정을 골랐는지, 무엇이 아직 증명되지 않았는지 말로 설명 가능

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

각 폴더 안의 `README.md`에 문제 정의·접근·결과·한계·AI 활용 구분이 정리되어 있습니다.

> **표현 경계**: WO-04의 워커는 LLM이 아닌 결정적 규칙이며 비용·지급은 모델링·합성 기록입니다. WO-05의 공격·방어는 합성 코퍼스 결과이며 실제 LLM·이메일·ATS 환경의 방어율이 아닙니다. WO-06은 공개 Lending Club 데이터의 사후 분석이며, 결과 관측 시점이 데이터에 없어 실제 배포 시점을 재현한 backtest가 아닙니다.

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
├── CLAUDE.md              # Codex 공통 규칙
├── README.md              # 이 파일
├── projects/
│   ├── wo-01-retrieval-eval/   # ✅ 검색 평가 하네스
│   ├── wo-02-hybrid-rag/       # ✅ 하이브리드 RAG
│   ├── wo-03-semantic-cache/   # ✅ 시맨틱 캐시
│   ├── wo-04-multi-agent/      # ✅ 멀티워커 오케스트레이션
│   ├── wo-05-injection-guard/  # ✅ 프롬프트 인젝션 가드레일
│   ├── wo-06-credit-scorecard/ # ✅ 신용평가 스코어카드
│   └── ...
└── track-d-sql/           # SQL·DB 학습 기록
```

---

## AI 활용 방식

모든 프로젝트 README에 **AI 활용 구분** 섹션이 있습니다.

| 직접 작성 | Codex 활용 |
|---|---|
| 목표·제약·Ship Gate·기술 선택·결과 해석·표현 경계 | 보일러플레이트·Docker·스캐폴딩·반복 계산·테스트 코드 |

코드가 왜 그렇게 작동하는지 설명할 수 없는 부분은 사용하지 않았습니다.

---

*마지막 업데이트: 2026-10-04*
