# WO-07 · 광고 CTR 예측과 확률 캘리브레이션

> 개인 프로젝트 · 대응 직군: 광고 ML 엔지니어 · 데이터: [Criteo Click Logs](https://huggingface.co/datasets/criteo/CriteoClickLogs), CC BY-NC-SA 4.0

## 문제 정의

클릭을 잘 순위화하는 모델이 입찰에 사용할 확률까지 정확하게 내는 것은 아니다. 예측 CTR에 클릭 가치를 곱해 입찰가를 정한다면 확률의 체계적 편향이 가치 추정에 영향을 준다. AUC와 함께 LogLoss, ECE, 예측 클릭 가치의 집계 오차를 측정한다.

## 가설

- LightGBM의 순위 성능을 유지하면서 사후 보정으로 확률 오차를 줄일 수 있다.
- 희소 범주와 결측 처리 규칙을 train에서만 학습하면 미래 데이터의 정보가 기준선에 새어 들어가지 않는다.
- Platt와 Isotonic은 같은 기준선에서도 다른 확률·가치 추정 결과를 낸다.

## 접근 / 시도 순서

1. **데이터 접근 확인:** Kaggle 대회 자료는 인증이 없어 다운로드할 수 없었다. Criteo가 공식 공개한 별도 Click Logs로 바꾸고 실제 파일, 라벨, 스키마, 결측, 범주 수를 검사했다. 근거는 [DATA_VALIDATION.md](DATA_VALIDATION.md)에 있다.
2. **기준선:** 앞선 두 날짜의 80,000행으로만 수치형 중앙값, 희소 범주 규칙, LightGBM을 학습했다. 기준선의 test ECE는 **0.009388**이고, 가정 클릭 가치의 합계는 관측 합계보다 낮았다.
3. **보정:** 그다음 날짜의 40,000행에 대해 기준 모델의 예측을 만든 뒤 Platt scaling과 Isotonic regression을 각각 적합했다. 기준 모델은 다시 학습하지 않았다.
4. **최종 비교:** 마지막 날짜의 같은 40,000행에서 세 방법을 평가했다. Platt는 AUC를 유지하면서 ECE를 **0.002513**, LogLoss를 **0.132260**으로 낮췄다. Isotonic도 확률 오차를 줄였지만 AUC가 약간 낮아졌다.
5. **시각화 수정:** 10개 동일 폭 ECE 구간으로는 낮은 CTR 영역의 곡선을 읽기 어려웠다. 그래프에만 20개 동일 인원수 구간을 사용했다. ECE의 정의와 실측값은 그대로 유지했다.

## 데이터

공식 Click Logs의 날짜별 Parquet 조각 4개를 실제 다운로드했다. 각 날짜에 고정 조각 하나를 선택하고 앞 40,000행만 사용했다. 원본 조각 전체는 3,010,082행이며, 이 실험에 입력한 행은 총 **160,000행**이다. `label` 1개, 수치형 13개, 해시 범주형 26개를 확인했다. 원본은 저장소에 포함하지 않는다.

| 구간 | 데이터 날짜 | 행 | 클릭 |
|---|---|---:|---:|
| train | 2015-02-15, 2015-02-16 | 80,000 | 2,477 |
| calibration | 2015-02-17 | 40,000 | 1,341 |
| test | 2015-02-18 | 40,000 | 1,244 |

날짜별 조각을 분리해 `train < calibration < test`를 지켰다. 조각 내부의 순서를 시간 경계로 해석하지 않았다. Criteo가 클릭과 비클릭을 서로 다른 비율로 부분 표본화했으므로 이 데이터의 클릭률을 실제 광고 트래픽의 CTR로 일반화하지 않는다.

## 파이프라인

`data/download.sh` → `data/audit.py` → `src/data.py` 날짜 분할 → `src/features.py` train 전용 중앙값·희소 범주 처리 → `src/models.py` LightGBM → `src/calibration.py` Platt/Isotonic → `src/metrics.py` AUC·LogLoss·ECE → `src/bidding.py` 가상 입찰 추정 오차 → `results/`.

범주형 값은 train 등장 횟수 10회 이상이며 열별 상위 512개인 경우만 개별 범주로 둔다. train에서 본 그 밖의 값은 `__RARE__`, 이후 처음 본 값은 `__UNKNOWN__`, 결측은 `__MISSING__`다. 변환기는 calibration/test에서 재학습되지 않는다. 모델은 고정 설정의 LightGBM 120개 트리를 사용한다.

ECE는 **10개 동일 폭 구간** `[0,0.1), …, [0.9,1]`에 대해 `Σ (구간 행 수 / 전체 행 수) × |평균 예측 확률 − 관측 클릭률|`로 계산한다. 빈 구간은 0을 기여하고 확률 1은 마지막 구간에 넣는다. [그래프](results/calibration_curve.png)는 **20개 동일 인원수 구간**으로 그려 낮은 CTR 영역을 보여준다.

## 결과 (Ship Gate 표)

세 방법을 동일한 test **40,000행**에서 측정했다. 측정 원본은 [experiment.json](results/experiment.json), [metrics.csv](results/metrics.csv)에 있다.

| 방법 | AUC | LogLoss | ECE ↓ |
|---|---:|---:|---:|
| LightGBM 기준선 | 0.668754 | 0.136838 | 0.009388 |
| Platt scaling | 0.668754 | **0.132260** | **0.002513** |
| Isotonic regression | 0.667469 | 0.132371 | 0.002525 |

Platt의 ECE는 기준선보다 **73.23%** 낮다. AUC가 같은 것은 순위와 확률 정확도가 별개임을 보여준다. 기본 보정 후보는 낮은 복잡도와 단조성을 근거로 **Platt로 사전 지정**했다. 이 test에서 Platt가 가장 낮은 LogLoss와 ECE를 보였다. test를 본 뒤 모델 설정이나 ECE 구간 수를 조정하지 않았다.

클릭 가치 **1,000 KRW**를 가정한 가상 입찰가 `가치 × 예측 CTR`의 집계 추정 오차는 다음과 같다. 관측 클릭 가치 총액은 세 방법 모두 **1,244,000 KRW**다.

| 방법 | 예측 클릭 가치 총액 (KRW) | 집계 편향 (KRW) | 절대 추정 오차 proxy (KRW) |
|---|---:|---:|---:|
| LightGBM 기준선 | 1,040,092.02 | -203,907.98 | 203,907.98 |
| Platt scaling | 1,313,429.77 | +69,429.77 | **69,429.77** |
| Isotonic regression | 1,313,961.63 | +69,961.63 | 69,961.63 |

Platt의 절대 집계 proxy는 기준선보다 **65.95%** 낮다. [bidding_analysis.csv](results/bidding_analysis.csv)와 [측정 보고서](results/report.md)에 계산 결과가 있다. 이것은 실제 낙찰가나 지출을 측정한 수치가 아니라 이 부분 표본에서 계산한 **가상 입찰 추정 오차**다.

## 시행착오와 해결

Kaggle 대회 자료에 접근하지 못한 상태에서 기존 검증 보고서만으로 결과를 만들 수 없었다. 공식 공개 Click Logs의 실제 날짜별 파일을 내려받고 고정된 조각과 체크섬을 기록했다. 기준선의 ECE와 집계 편향을 먼저 확인한 뒤, 같은 기준선에 두 보정기를 적용했다. Isotonic은 계단형 매핑으로 동점 예측을 만들어 AUC가 소폭 낮아졌고, Platt는 이 test에서 순위를 유지했다.

## 한계

이 결과는 4개 날짜의 조각 하나씩만 사용한 부분 표본 평가다. 원본 라벨의 비대칭 부분 표본화, 단일 시간 분할, 세그먼트별 오차, 확률 구간에 따른 ECE 변화는 외부 적용을 제한한다. 입찰 proxy는 개별 오차가 상쇄되는 합계 지표이며 실제 경매 비용이나 ROI를 나타내지 않는다. 필요한 추가 데이터와 해석 범위는 [MEASUREMENT_BOUNDARY.md](MEASUREMENT_BOUNDARY.md)에 정리했다.

## 재현

Python 3.11과 Docker Compose 환경에서 실행한다.

```bash
cd projects/wo-07-ctr-calibration
bash data/download.sh
docker compose build
docker compose run --rm experiment
docker compose run --rm test
```

pytest 14개가 통과했다. 테스트는 날짜 중복·역순, train 전용 범주 규칙, ECE 경계와 빈 구간, 보정기의 test 라벨 비사용, 가상 입찰 proxy, 결과 파일과 README 수치 계약을 확인한다.

## 개발 방식 (AI 활용 구분)

| 사용자 제공·판단의 출처 | Codex가 수행한 작업 |
|---|---|
| 프로젝트 목표, 포트폴리오 규칙, 결과 보고 기준을 제공 | 실제 데이터 접근과 스키마 검증, 대체 데이터 선택, 코드·테스트·컨테이너·측정 문서 작성 |

모든 수치는 실행 결과 파일에서 옮겼다. 사용자가 직접 코드를 작성하거나 실험 수치를 측정했다고 주장하지 않는다.

## 관련 개념

**AUC**는 양성과 음성의 상대적 순위, **LogLoss**는 참 라벨에 부여한 확률의 손실, **ECE**는 예측 구간별 평균 확률과 관측 빈도의 차이를 요약한다. **Platt scaling**은 모델 점수에 시그모이드 매핑을 맞추고, **Isotonic regression**은 단조 계단 함수를 맞춘다. 보정기는 독립된 calibration 구간에서만 학습해야 한다.

## English Technical Summary

This project evaluates click probability calibration on four dated shards of Criteo Click Logs. A LightGBM baseline is trained on 80,000 earlier impressions, while Platt scaling and isotonic regression are fitted on a separate 40,000-impression calibration partition. On an untouched 40,000-impression test partition, Platt scaling preserves AUC at 0.668754 and reduces ECE from 0.009388 to 0.002513. A hypothetical bid-value aggregate error proxy falls from 203,907.98 to 69,429.77 KRW under an assumed 1,000 KRW click value. These are sample-specific estimates, not observed auction costs or production CTR.
