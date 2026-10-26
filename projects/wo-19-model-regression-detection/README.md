# WO-19 · 모델 회귀(regression) 탐지

> 개인 프로젝트 · 대응 직군: MLOps · 데이터: WO-07에서 감사한 Kaggle Avazu CTR Prediction 평가 표본; 대회 이용 조건 적용

**골든셋 기준**: 새 레이블을 만들지 않고 WO-07이 검증한 Avazu 표본의 마지막 두 평가 구간 201,137행을 고정한다. 버전 A는 WO-07 LightGBM 기준 모델의 0.5 임계값 예측이다. 회귀는 사전 지정한 `device_type=0`에서 정확도가 5%p 이상 낮고, 세 평가 세그먼트에 대한 다중 검정을 보정한 단측 p-value가 0.05 미만인 경우로 정의한다. 버전 B의 통제 회귀 크기는 10%p로 주입한다. 이 골든셋은 회귀 탐지기를 평가하며 새 모델의 실서비스 성능을 추정하지 않는다.

## 문제 정의

전체 정확도(accuracy)만 비교하면 일부 입력 세그먼트(segment)의 성능 저하가 다른 곳의 개선으로 상쇄될 수 있다. 이 프로젝트는 같은 평가 행에 대한 모델 버전(model version)별 정답 여부를 짝지어 비교하고, 실질 크기와 통계적 근거를 함께 만족하는 세그먼트 회귀를 찾는다.

## 가설

- 세그먼트 하나에서 정확도를 10%p 낮추고 다른 세그먼트에서 같은 수의 오류를 보정하면, 전체 정확도는 기준선과 같아도 세그먼트 검정은 회귀를 찾는다.
- 각 세그먼트의 정확도를 보존한 대조 버전은 고정 평가셋에서 회귀로 표시되지 않는다.
- 세그먼트당 평가 표본이 늘면 탐지력(power)이 높아진다. 쌍체 t-검정과 부트스트랩(bootstrap)의 거짓 양성률은 작은 표본에서 차이가 날 수 있다.

## 접근 — 시도 순서

1. **기존 자산을 골든셋으로 고정:** WO-07의 Avazu 시간 분할, 전처리, LightGBM 기준 모델을 그대로 호출했다. 원본 및 파생 행 데이터는 별도 프로젝트로 복사하거나 커밋하지 않는다.
2. **회귀 기준을 사전 지정:** 원시 정확도 하락 5%p 이상과 유의수준 0.05를 함께 요구한다. `device_type` 중 표본 1,000행 이상인 값 `0`, `1`, `4`를 검정 가족으로 삼고 Holm 보정을 적용한다. 641행인 값 `5`는 기준 미달로 검정에서 제외한다.
3. **세 버전 구성:** A는 기준 모델, C는 세그먼트별 정답·오답을 같은 수만큼 교환해 정확도를 보존한 무회귀 대조군이다. B는 `device_type=0`에서 정답 10%를 오답으로 바꾸고, `device_type=1`에서 같은 수의 오답을 정답으로 바꿔 전체 정확도를 보존한다.
4. **검정과 표본 크기 실험:** 같은 행의 정답 여부 차이에 대한 단측 쌍체 t-검정과 백분위 부트스트랩을 비교했다. `50/200/1,000`행을 세그먼트별로 복원 추출해 각 크기에서 2,000회 모의 반복했다.
5. **실패 후 재현 환경 보완:** 첫 컨테이너 실행에서 OpenMP 런타임, PyArrow, scikit-learn 누락을 차례로 발견했다. WO-07 로더·모델을 사용하는 실제 실행으로 의존성을 확인하고 Docker 이미지에 고정했다. 상세 근거는 [판단 장면](CLAUDE_HANDOFF.md)에 있다.

## 데이터

WO-07에서 Avazu `train.gz`의 체크섬·스키마·행 수·순서를 검증하고 `crc32(id) % 40 == 17`로 만든 고정 표본을 사용한다. 학습 구간은 596,330행, 보정 구간은 213,049행이며, WO-19은 기존 WO-07 LightGBM 기준 모델을 학습 구간에 다시 적합하고 마지막 두 평가 구간 201,137행만 분석한다. 본문에서 사용한 세그먼트 표본 수는 `device_type=0: 10,236`, `1: 186,600`, `4: 3,660`, `5: 641`이다. 행 단위 예측이나 원본 데이터는 결과물에 저장하지 않는다.

`data/README.md`에는 입력 파일 위치와 재현 절차가 있다. 평가 표본은 WO-07 `data/avazu_sample.csv.gz`에 준비되어 있어야 한다.

## 파이프라인

WO-07 표본 로드 → 기존 시간 분할·train 전용 범주 변환기 → 기존 LightGBM 기준 모델 → 평가 행별 정확도 벡터 A → 레이블 기반 통제 변형 B/C → 세그먼트별 단측 검정·다중 검정 보정 → 크기별 반복 표본 추출 → 집계 결과 JSON/CSV.

정확도 차이는 `버전 − 기준선`의 퍼센트 포인트(percentage point)다. 쌍체 t-검정(paired t-test)은 3개 세그먼트에 Holm step-down 보정(Holm step-down correction), 부트스트랩(bootstrap)은 가족 단위 오류율(family-wise error rate) 0.05를 위한 Bonferroni 보정(Bonferroni correction) 단측 상한을 사용한다. 운영 회귀 플래그는 보정 검정 통과와 관측 하락 5%p 이상을 모두 요구한다. 모의 실험의 거짓 양성률(false-positive rate)은 이 운영 플래그와 통계적 유의성만 보는 플래그를 별도로 집계한다.

## 결과 (Ship Gate 표)

### 전체 평균은 세 버전을 구분하지 못함

| 범위 | 행 수 | 버전 A 기준 | 버전 C 무회귀 | 버전 B 주입 회귀 |
|---|---:|---:|---:|---:|
| 전체 | 201,137 | 83.9025% | 83.9025% | 83.9025% |
| `device_type=0` | 10,236 | 79.6893% | 79.6893% | 69.6854% |
| `device_type=1` | 186,600 | 84.0225% | 84.0225% | 84.5638% |
| `device_type=4` | 3,660 | 88.5792% | 88.5792% | 88.9617% |

버전 B의 `device_type=0` 정확도는 **10.0039%p** 하락했다. 이를 `device_type=1`과 `4`의 합계 정확도 개선으로 상쇄해 전체 정확도를 같게 만들었다. 대조군 C는 각 검정 세그먼트 안에서 정확도를 보존했다.

### 전체 평가셋 검정

| 비교 (세그먼트 `0`) | 정확도 차이 | 단측 쌍체 t p-value | Holm 보정 p-value | 쌍체 부트스트랩 95% 구간 |
|---|---:|---:|---:|---:|
| C − A | 0.0000%p | 0.5 | 1.0 | -0.6057~+0.6350%p |
| B − A | -10.0039%p | 6.84×10⁻²³⁷ | 2.05×10⁻²³⁶ | -10.5998~-9.4468%p |

**측정 방식**: 동일 평가 행의 이진 정답 여부 차이를 비교했다. 부트스트랩은 1,000회이며, 다중 검정 보정 상한은 별도로 계산했다. 고정 C 대조군은 t-검정과 보정 부트스트랩 모두 회귀 플래그를 내지 않았다.

### 세그먼트당 표본 크기별 거짓 양성률과 탐지력

| 세그먼트당 행 수 | 방법 | C에서 통계적 유의성만 본 거짓 양성률 | C에서 운영 회귀 플래그 거짓 양성률 | B 회귀 탐지력 |
|---:|---|---:|---:|---:|
| 50 | 쌍체 t + Holm | 3.65% | 3.65% | 56.20% |
| 50 | 부트스트랩 + Bonferroni | 5.45% | 5.45% | 69.15% |
| 200 | 쌍체 t + Holm | 5.45% | 4.30% | 99.65% |
| 200 | 부트스트랩 + Bonferroni | 4.90% | 3.85% | 99.65% |
| 1,000 | 쌍체 t + Holm | 5.15% | 0.00% | 100.00% |
| 1,000 | 부트스트랩 + Bonferroni | 4.65% | 0.00% | 100.00% |

**측정 방식**: 표본 크기별 독립 복원 추출(with-replacement sampling) 2,000회. 통계적 유의성 거짓 양성률은 보정 p-value만으로, 운영 거짓 양성률은 여기에 관측 하락 5%p 기준까지 적용해 계산했다. 각 비율의 95% Wilson 구간(Wilson score interval)은 [원 결과 JSON](results/experiment_results.json)에 있다. 운영 회귀 플래그는 `하락 ≥5%p`와 보정 검정 통과를 함께 요구한다.

유의성만 비교하면 두 방법 모두 표본 200개 이상에서 명목 5%에 가까운 가족 거짓 양성률을 보였다. 50개에서는 쌍체 t-검정이 3.65%로 보수적이었고 부트스트랩은 5.45%였다. 10%p 주입 회귀의 운영 탐지력은 50개에서 각각 56.20%, 69.15%였고 200개에서 둘 다 99.65%였다. 이 결과만으로 모든 분포에서 한 검정이 더 낫다고 결론 내리지 않는다.

## 시행착오와 의사결정

처음에는 버전 B에 정확히 5%p만 회귀를 주입했다. 표본당 50행에서 통계적 유의성만 요구하면 t-검정 탐지력 10.20%, 부트스트랩 21.70%로 낮았다. 회귀 정의가 “5%p 이상”인데 실험 변화도 경계값에 놓이면 측정 잡음 때문에 운영 플래그 성능 해석이 흐려진다고 판단했다. 최종 실험은 탐지 기준을 5%p로 유지하고 B 변화는 10%p로 높여, 경계 기준과 검정력을 구분했다. 초기 측정은 최종 Ship Gate에 섞지 않았다.

또한 통계적 유의성만의 거짓 양성률과 운영 기준까지 적용한 거짓 양성률을 나눴다. 1,000행 조건은 유의성 검정에서 5% 근처의 가족 오류율을 유지했지만, 관측 효과 5%p 기준까지 요구하자 이 통제된 무회귀 반복에서 운영 플래그는 0/2,000이었다. 이는 우연에 의한 p-value 유의성과 실질적 크기 기준이 다른 역할을 한다는 결과다.

## 측정 경계 (한계)

**다음 단계**: 실제 재학습된 모델 버전의 예측을 입력하고, 모델·날짜 단위 군집 재표집 및 불균형 세그먼트 기준을 비교한다. 현재 버전 B/C는 평가 레이블을 이용해 정답 여부를 직접 바꾼 통제 시나리오이며, 예측 확률·손실·실제 학습 변화를 재현하지 않는다. 정확도 임계값 0.5와 하나의 고정 Avazu 홀드아웃에 조건부인 탐지 결과다.

## 재현

Python 3.11과 Docker Compose를 사용한다. 데이터 표본은 먼저 WO-07 지침에 따라 준비한다.

```bash
cd projects/wo-07-ctr-calibration
docker compose run --build --rm avazu

cd ../wo-19-model-regression-detection
docker compose run --build --rm test
docker compose run --build --rm experiment
```

측정 결과는 `results/experiment_results.json`, `results/version_metrics.csv`, `results/sample_size_rates.csv`에 기록한다. `results/`에는 행 단위 원본이나 예측을 남기지 않는다.

## 개발 방식 (AI 활용 구분)

| 사용자가 제공·결정한 것 | Codex가 구현·검증한 것 |
|---|---|
| WO-19 목표·Ship Gate·공통 작업 규칙, WO-07에서 감사한 데이터 자산의 재사용 범위 | 골든셋 연결, 통제된 A/B/C 변형, paired t-test·부트스트랩·Holm/Bonferroni 보정, 표본 크기 모의 실험, 문서·테스트 |

세그먼트, 임계값과 실험 결과 해석은 작업지시서에서 정한 범위와 실제 실행 결과로 기록했다. 별도의 사용자 판단을 받은 것은 없다.

## 용어집

| 용어 | 뜻 |
|---|---|
| 모델 버전 (model version) | 같은 평가 입력에 대해 변경 전후 시스템이 만든 예측 집합. 이 프로젝트에서는 기준·무회귀·주입 회귀를 비교한다 |
| 세그먼트 (segment) | 공통 속성을 가진 평가 입력의 하위 집단. `device_type`별로 정확도 변화를 따로 검사한다 |
| 골든셋 (golden set) | 평가 기준과 레이블이 고정된 검증 데이터. 이 프로젝트는 WO-07의 감사된 Avazu 홀드아웃을 재사용한다 |
| 쌍체 t-검정 (paired t-test) | 같은 행에서 두 버전의 정답 여부 차이 평균이 0보다 낮은지 검사한다 |
| 부트스트랩 (bootstrap) | 관측 차이를 복원 추출해 효과 구간을 계산하는 방법. 작은 세그먼트의 불확실성을 수치로 보여준다 |
| Holm 보정 (Holm step-down correction) | 여러 세그먼트를 동시에 검사할 때 가족 단위 거짓 양성률을 제어하는 순차 p-value 보정이다 |
| Bonferroni 보정 (Bonferroni correction) | 여러 검정의 유의수준을 나눠 전체 거짓 양성률을 제한한다. 부트스트랩 상한의 세그먼트 가족 기준으로 사용했다 |
| 퍼센트 포인트 (percentage point) | 비율 두 개의 산술 차이다. 여기서는 정확도 변화의 절대 크기를 백분율 단위로 나타낸다 |
| 유의수준 (significance level) | 귀무가설이 맞을 때 검정이 거짓 양성을 허용하는 기준이다. 이 실험은 가족 단위 기준을 0.05로 설정했다 |
| p-value (p-value) | 귀무가설에서 관측 차이만큼 극단적인 결과가 나올 확률이다. 낮은 값만으로 회귀의 크기나 실무 의미를 판단하지 않는다 |
| 몬테카를로 반복 (Monte Carlo simulation) | 확률적 재표집을 여러 번 실행해 거짓 양성률과 탐지력을 추정하는 절차다 |
| Wilson 구간 (Wilson score interval) | 반복 실험에서 측정한 비율의 표본 오차를 나타내는 구간 추정치다 |
| 거짓 양성률 (false-positive rate) | 회귀가 없는 대조군을 회귀로 잘못 표시한 반복 실험의 비율 |
| 탐지력 (statistical power) | 주입 회귀가 있는 경우 회귀 플래그를 올바르게 낸 반복 실험의 비율 |

## English Technical Summary

This project reuses the audited Avazu holdout and LightGBM baseline from WO-07 to benchmark segment-level regression detection. The fixed holdout contains 201,137 rows. Version B injects a 10.0039 percentage-point accuracy drop into `device_type=0` while compensating errors in control segments, leaving global accuracy unchanged at 83.9025%. Version C preserves accuracy inside every eligible segment. A paired one-sided t-test with Holm correction and a paired bootstrap with Bonferroni family-wise bounds are evaluated over 2,000 resampled trials at segment sizes 50, 200, and 1,000. For the predeclared 5-point practical threshold, power rises from 56.20%/69.15% at 50 rows to 99.65% for both methods at 200 rows. The label-guided mutations benchmark detector behavior on one fixed holdout; they do not estimate realistic model retraining performance.
