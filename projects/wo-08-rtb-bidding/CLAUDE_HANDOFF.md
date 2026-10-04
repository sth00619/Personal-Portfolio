# WO-08 전달 요약

- 브랜치: `dev/wo-08`
- 코드: `projects/wo-08-rtb-bidding/src/experiment.py`
- 실행: `python data/download.py` → `docker compose run --build --rm experiment` → `docker compose run --build --rm test`
- 원본 경로: 공식 iPinYou 데이터 호스트는 연결되지 않았고, Figshare의 원본 `imp`·`clk` 보관본에 접근했다. 네 클릭 로그와 전체 평가 노출 로그는 원본 MD5와 일치한다.
- 예산: 학습 접두 구간의 광고주 1458 지출을 전체 시간으로 환산한 값의 50%, 로그 가격 단위로 5,450.630.

| 정책 | 클릭 이벤트 | 지출 | eCPC | 낙찰 노출 |
|---|---:|---:|---:|---:|
| 상수 입찰 | 85 | 5,450.629 | 64.125 | 126,326 |
| 선형 pCTR | 76 | 5,450.629 | 71.719 | 114,467 |
| ORTB | 79 | 5,450.628 | 68.995 | 115,497 |
| 페이싱 ORTB | 83 | 5,450.628 | 65.670 | 162,736 |

- 지출 곡선: `results/hourly_spend.png`, 수치 `results/hourly_spend.csv`
- 관측 낙찰가 곡선: `results/win_curve.png`, 수치 `results/win_curve.csv` (조건부 CDF, ORTB 적합 RMSE 0.114)
- 전체 수치와 데이터 감사: `results/report.json`, `DATA_VALIDATION.md`
- 시행착오: 가공된 대안 보관본에는 낙찰가가 없어 원본 보관본으로 전환했다. 원본에도 패배 경매 낙찰가는 없으므로 가상 입찰을 기록 입찰가 이하로 제한했다. 정적 ORTB·선형 정책은 평가 로그의 중간 구간에 예산을 소진했고, 페이싱 ORTB는 전 시간대에 지출했다.
- 해석: 상수 입찰이 클릭 85회로 최다였고 페이싱 ORTB와의 차이는 2회다. 평가 pCTR AUC 0.577, 승률 함수 적합 RMSE 0.114로 예측·함수 가정의 한계가 있다. 페이싱의 지출 분산 개선을 클릭 증가로 표현하면 안 된다.
- 학습점: 예산 제약을 만족하는 것과 클릭 효율을 높이는 것은 별개이며, 오프라인 재생의 관측 지원 범위를 먼저 정의해야 결과를 해석할 수 있다.
