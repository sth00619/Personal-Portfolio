# WO-09 전달 요약

- 브랜치: `dev/wo-09`
- 실행: `docker compose run --build --rm download` → `docker compose run --build --rm experiment` → `docker compose run --build --rm test`
- 코드: `src/experiment.py`(후보 생성·LightGBM·BTS 정책 재구성), `src/ope.py`(OBP·부트스트랩), `run.py`(실험)
- 데이터: ZOZO Open Bandit Dataset Men 전체 로그. Random 452,949건, BTS 4,077,727건. 원본은 저장소에서 제외하며 `DATA_VALIDATION.md`에 CRC와 분할을 기록.
- BTS 실제 클릭률: 위치 표준화 `0.7029%`(독립 검증 607,536건, 클릭 4,270건)

| 추정량 | BTS 추정 | 95% 부트스트랩 | 실측 대비 절대 오차 |
|---|---:|---:|---:|
| DM | 0.4933% | 0.4931–0.4935% | 0.2096%p |
| IPS | 0.7315% | 0.6222–0.8412% | 0.0287%p |
| SNIPS | 0.7340% | 0.6323–0.8387% | 0.0312%p |
| DR | 0.7300% | 0.6260–0.8349% | 0.0272%p |

| 추천 | 후보 Recall@10 | 관측 클릭 nDCG@3 |
|---|---:|---:|
| 인기도 | 0.3427 | 0.0604 |
| 인기도+친화도 CF → LightGBM | 0.3478 | 0.0601 |

- 그래프: `results/ope_benchmark.png`, `results/ranking_metrics.png`; 원 수치 `results/report.json` 및 CSV 3종
- 첫 시도: OBP 고정 초기 prior의 실제 BTS 행동 분포 TV 거리 `0.413`. 정책 복제 오차가 추정량 비교에 섞임.
- 수정: 같은 평가 기간 BTS 로그에서 행동만으로 시간대·위치별 정책을 재구성하고 나머지 클릭을 독립 보관. 정책 TV 거리 `0.036`.
- 결과·의사결정: DR은 실측과 가장 가까우며 IPS와 구간이 겹친다. DM의 클릭 모델은 평가 클릭률을 낮게 예측했고 DM 구간은 실측을 놓쳤다. 추천 후보 Recall은 소폭 높아졌지만 nDCG는 개선되지 않았다.
- 신규 2단 정책: DR `0.6351%`(95% `0.3812–0.8741%`), 직접 관측한 배포 클릭률은 없음. Random 실측 `0.5645%`와의 차이를 확정적 개선으로 표현하지 않음.
- 학습점: 정책 복제 오차와 OPE 추정 오차를 분리해 확인하고, 후보 발견과 최종 순위 품질을 따로 검증해야 한다.
