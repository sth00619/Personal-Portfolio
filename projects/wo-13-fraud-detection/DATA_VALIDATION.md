# WO-13 데이터 검증 기록

## 출처와 이용 조건

- 기준 출처: [IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data)
- 주관: IEEE Computational Intelligence Society, Vesta Corporation
- 이용 조건: Kaggle competition rules
- 전송 경로: [`aliceczr/ieee-fraud-detection`](https://huggingface.co/datasets/aliceczr/ieee-fraud-detection/tree/main) 공개 미러

Kaggle 원본 페이지는 로그인과 대회 규칙 동의를 요구한다. 다운로드 스크립트는 원래 파일명과 크기를 유지한 공개 미러를 전송 경로로 사용하고, SHA-256을 고정한다. 원본 파일은 Git에 포함하지 않는다.

## 파일 무결성

| 파일 | 데이터 행 | 열 | 바이트 | SHA-256 |
|---|---:|---:|---:|---|
| `train_transaction.csv` | 590,540 | 394 | 683,351,067 | `3a5c83ab6b3cc13dcabe5ffa9f522307fd5f7f7b6e6f6a60c32284ca6283d642` |
| `train_identity.csv` | 144,233 | 41 | 26,529,680 | `b63c725d8377be90a995268d97f347c17d456b95db45807adcf9f59cd603c37c` |

## 조인과 레이블 검증

| 항목 | 관측값 |
|---|---:|
| 거래 행 | 590,540 |
| 사기 거래 | 20,663 |
| 사기 비율 | 3.4990% |
| 조인 뒤 전체 열 | 434 |
| `TransactionID`, `isFraud` 제외 예측 피처 | 432 |
| 시간 학습 행 | 472,432 |
| 시간 평가 행 | 118,108 |
| 시간 평가 사기 거래 | 4,064 |
| 시간 평가 사기 비율 | 3.4409% |
| 학습 구간 최대 `TransactionDT` | 12,192,842 |
| 평가 구간 최소 `TransactionDT` | 12,192,900 |

`train_transaction`과 `train_identity`를 `TransactionID`로 왼쪽 조인해 거래 행 수를 유지했다. 작업지시서의 피처 수와 달리 실제 파일 조인에서는 전체 434열, 식별자와 레이블을 제외하면 432개 예측 피처가 관측됐다. 모델과 문서는 실제 스키마를 기준으로 한다.

