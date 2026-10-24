# WO-12 데이터 검증 기록

## 출처와 이용 조건

- 기준 출처: [M5 Forecasting Accuracy competition](https://www.kaggle.com/competitions/m5-forecasting-accuracy/data)
- 주관: Makridakis Open Forecasting Center, University of Nicosia
- 이용 조건: Kaggle competition rules
- 전송 경로: [`sktime/tsf-datasets`](https://huggingface.co/datasets/sktime/tsf-datasets/tree/main/m5-forecasting-accuracy) 공개 미러
- 공식 구조 확인: [M5 Competitors Guide](https://storage.googleapis.com/kaggle-forum-message-attachments/772349/15032/M5-Competitors-Guide-Final-10-March-2020.pdf)

Kaggle 원본 페이지는 로그인과 대회 규칙 동의를 요구한다. 재현 스크립트는 같은 이름과 구조의 공개 미러 파일을 받고, 크기와 SHA-256을 검증한다. 원본 파일은 Git에 포함하지 않는다.

## 파일 무결성

| 파일 | 바이트 | SHA-256 | 사용 범위 |
|---|---:|---|---|
| `sales_train_evaluation.csv` | 121,736,518 | `4b4a47c44c38380d2a9168216fea8c9ff2f31b1ddb772f8a0995952a038b8aa0` | 판매량, 품목·매장·카테고리 식별자 |
| `calendar.csv` | 103,469 | `d12b5914ef03e66649adf5dd9e996e6602251c22b7a6af8f1f7e3aa12f8860f5` | 요일, 월, SNAP, 이벤트 여부 |

## 실험 추출 검증

| 항목 | 관측값 |
|---|---:|
| 선택 매장 | `CA_1` |
| 선택 카테고리 | `FOODS` |
| 품목 수 | 1,437 |
| 품목당 판매 관측일 수 | 1,941 |
| 워크포워드 분할 수 | 3 |
| 분할별 예측 구간 | 28일 |
| 품목 레벨 평가 관측 수 | 120,708 |
| 집계 레벨 평가 관측 수 | 84 |

품목 레벨 평가 분모는 `1,437개 × 28일 × 3분할 = 120,708건`, 집계 레벨 평가 분모는 `1개 시계열 × 28일 × 3분할 = 84건`으로 코드 출력과 일치한다.
