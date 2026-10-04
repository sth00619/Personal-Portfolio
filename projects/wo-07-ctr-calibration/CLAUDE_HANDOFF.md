# WO-07 전달 자료

- 브랜치: `dev/wo-07`
- 프로젝트: `projects/wo-07-ctr-calibration/`
- 주 실험 데이터: [Criteo Click Logs 공식 배포](https://ailab.criteo.com/download-criteo-1tb-click-logs-dataset/) → `criteo/CriteoClickLogs`; CC BY-NC-SA 4.0. 처음에는 Kaggle 인증이 없어 공식 Criteo 데이터로 진행했다. 원본 Parquet 4개를 다운로드하고 SHA-256을 검증했다. 독립 검증에는 사용자가 별도로 제공한 Avazu 대회 로그를 사용했다. 모든 원본은 Git 추적에서 제외했다.
- 표본: 날짜별 고정 조각 하나의 앞 40,000행, 총 160,000행. 전체 데이터 결과가 아니다.
- 날짜 분할: train 2015-02-15~16, 80,000행/2,477클릭; calibration 2015-02-17, 40,000행/1,341클릭; test 2015-02-18, 40,000행/1,244클릭. 날짜별 조각을 분리했고 조각 안의 행 순서는 시간 분할의 근거로 쓰지 않았다.

## Ship Gate 실측

| 방법 | AUC | LogLoss | ECE (10개 동일 폭 구간) |
|---|---:|---:|---:|
| LightGBM 기준선 | 0.668754 | 0.136838 | 0.009388 |
| Platt scaling | 0.668754 | 0.132260 | 0.002513 |
| Isotonic regression | 0.667469 | 0.132371 | 0.002525 |

이 표는 모두 동일한 test 40,000행에서 측정했다. 기본 보정 후보는 낮은 복잡도와 단조성을 근거로 Platt로 사전 지정했다. 이 실험에서 AUC를 유지했고, 세 방법 가운데 LogLoss와 ECE가 가장 낮았다. 이는 하나의 test 표본에서 관찰한 결과이며, test에 맞춰 하이퍼파라미터를 조정하지 않았다.

## 가상 입찰 추정 오차

클릭 1회 가치 1,000 KRW를 가정한 집계 proxy다. 기준선 편향 **-203,907.98 KRW**, 절대 오차 **203,907.98 KRW**; Platt 편향 **+69,429.77 KRW**, 절대 오차 **69,429.77 KRW**; Isotonic 편향 **+69,961.63 KRW**, 절대 오차 **69,961.63 KRW**. Platt의 절대 집계 오차는 기준선보다 65.95% 낮다. 이 숫자는 실제 광고비 절감액이 아니다.

그래프: `results/calibration_curve.png` (test에서 20개 동일 인원수 구간). 측정 원본: `results/experiment.json`, `results/metrics.csv`, `results/bidding_analysis.csv`, `results/data_audit.json`. 데이터 검증 세부 근거는 `DATA_VALIDATION.md`, 해석 경계는 `MEASUREMENT_BOUNDARY.md`.

## 접근과 시행착오

1. 첫 접근에서는 Kaggle 인증 정보가 없어 Criteo/Avazu API가 401을 반환했다. Kaggle Criteo 대회 파일은 배포 페이지에서도 더 이상 제공하지 않는다.
2. Criteo 공식 공개 Click Logs로 전환해 날짜별 파일, 실제 스키마, 라벨, 결측과 카디널리티를 검사했다.
3. 기준선은 test의 클릭 가치 합계를 낮게 예측했고, 보정 전 ECE가 0.009388이었다.
4. train에만 적합한 희소 범주 규칙을 고정하고 calibration에만 보정기를 적합했다. Platt와 Isotonic을 같은 test에서 비교했다.
5. 10개 동일 폭 ECE 구간은 낮은 CTR 영역의 그래프를 읽기 어려워, **그래프만** 20개 동일 인원수 구간으로 바꿨다. ECE 정의와 test 결과는 바꾸지 않았다.
6. 사용자가 Kaggle Avazu `train.gz` 원본을 제공한 뒤, 원본 전체의 해시·시간 순서를 검증하고 별도 날짜 분할 실험을 수행했다. Criteo의 기준 수치는 변경하지 않았다.

## 재현과 검증

```bash
cd projects/wo-07-ctr-calibration
bash data/download.sh
docker compose build
docker compose run --rm experiment
docker compose run --rm test
```

Docker Compose에서 pytest **19개 통과**를 확인했다. `tests/test_regression.py`는 ECE 값 제거 시 실패한다. 원본 Parquet, Avazu 압축 파일, 인증 정보, 모델 바이너리는 커밋하지 않았다.

README와 Notion 문구에는 “실제 광고비 절감”, “실제 과다지출”, “전체 Criteo 데이터 검증”, “실제 트래픽 CTR”을 사용하면 안 된다. 다음 단계는 더 많은 날짜별 조각의 반복 검증, 구간별 확률 평가, 실제 경매 로그와 표본화 비율을 확보한 비용 평가다.

## Avazu 독립 검증 추가 결과

- 원본: Kaggle Avazu `train.gz`, **40,428,967행 / 6,865,066클릭**. SHA-256과 압축 무결성 검증. 원본·추출 표본은 Git에서 제외.
- 표본: `crc32(id) % 40 == 17`로 **1,010,516행**. 학습 **596,330행**, 보정 **213,049행**, 뒤쪽 평가 **201,137행**. 각 구간은 날짜가 겹치지 않음.
- 최종 평가 기준선 AUC **0.721701**, LogLoss **0.401317**, ECE **0.012503**.
- Platt AUC **0.721701**, LogLoss **0.400916**, ECE **0.009273**. Isotonic AUC **0.721530**, LogLoss **0.400570**, ECE **0.004175**.
- 기준선 대비 ECE 감소의 날짜별 층화 부트스트랩 95% 구간: Platt **0.001898–0.004475**, Isotonic **0.006557–0.009134**. 모델 적합 불확실성은 포함하지 않음.
- 두 평가 날짜 각각에서 보정법의 LogLoss·ECE 개선이 관측됨. Avazu에서는 Isotonic이 확률 지표에서 앞섰고 AUC는 소폭 낮았다. Criteo와 Avazu의 점수를 직접 대조해 우위를 주장하지 않는다.
- 자료: `AVAZU_VALIDATION.md`, `results/avazu/report.json`, `metrics.csv`, `per_day_metrics.csv`, `calibration_curve.png`. 실행: `docker compose run --build --rm avazu`.
