# 데이터 검증: Criteo Click Logs

## 판정

**주 실험의 대체 채택.** 처음에는 Kaggle 인증 정보가 없고 API 요청이 HTTP 401을 반환해 대회 파일을 확보할 수 없었다. 주 실험에는 [Criteo 공식 배포 페이지](https://ailab.criteo.com/download-criteo-1tb-click-logs-dataset/)가 연결한 [Criteo Click Logs](https://huggingface.co/datasets/criteo/CriteoClickLogs)를 사용한다. 이는 Kaggle Criteo 대회 데이터와 **다른 데이터셋**이다. 사용자가 별도로 내려받아 제공한 Avazu 대회 파일은 이후 **독립 검증**에 사용했고, 원본 검증은 [AVAZU_VALIDATION.md](AVAZU_VALIDATION.md)에 기록했다.

공식 설명은 이 데이터가 디스플레이 광고 노출과 클릭 피드백으로 구성되고, 24일의 일자별 데이터이며, 원본 행이 시간순이라고 밝힌다. 현재 배포 형식은 날짜별 디렉터리 안의 여러 Parquet 조각이다. 조각 **안**의 순서를 시간 정보로 가정하지 않고, 날짜가 다른 조각 사이의 선후 관계만 분할에 사용한다.

## 배포와 이용 조건

| 항목 | 확인 결과 |
|---|---|
| Kaggle CLI | 인증 파일과 `KAGGLE_USERNAME`, `KAGGLE_KEY`, `KAGGLE_API_TOKEN` 모두 없음. 초기 비인증 API 요청 HTTP 401. Avazu 파일은 사용자가 브라우저로 직접 다운로드 |
| 채택 데이터 | `criteo/CriteoClickLogs` 공개 파일 다운로드 성공. 별도 계정 불필요 |
| 라이선스 | [데이터 카드](https://huggingface.co/datasets/criteo/CriteoClickLogs/blob/main/README.md)의 CC BY-NC-SA 4.0. 연구·비상업 목적, 출처 표시. 원본 재배포 없이 Git에서 제외 |
| 다운로드 | `bash data/download.sh` — 날짜별로 고정된 Parquet 조각 하나씩 다운로드하고 SHA-256 검증 |

## 실제 파일과 무결성

| 날짜별 로컬 파일 | 압축 크기(byte) | Parquet 메타데이터 행 수 | SHA-256 |
|---|---:|---:|---|
| `2015-02-15.parquet` | 47,582,883 | 762,070 | `c99c772478979160b28b94692ff6f45b32fb3511c6de9dda7607096c2075f91d` |
| `2015-02-16.parquet` | 48,660,663 | 776,127 | `fa2086237e6f0d1e2085bbe0dd526806ac61853aab4f0c5a06468675cf8d4401` |
| `2015-02-17.parquet` | 47,879,374 | 766,723 | `0d8aaa25a4c412ce030dc889d2d853ec0f4128cc435af01819bea015f90cd08c` |
| `2015-02-18.parquet` | 44,082,134 | 705,162 | `f082372f26c0f34063c8989bcc47b279d58b0215bcc1fdb0f252accf25dbbdfb` |

원본 조각 4개의 합계는 3,010,082행, 압축 188,205,054 byte다. 전체 24일의 전체 파일 수나 행 수를 스캔한 결과로 확대하지 않는다. 파일별 공식 경로는 `data/download.sh`에 고정했다.

## 스키마와 품질

`docker compose run --rm -v "$PWD:/app" experiment python data/audit.py`로 각 파일의 **앞 40,000행**을 검사했다. 결과 원본은 `results/data_audit.json`에 있다.

- 40개 컬럼: `label`(int32), `integer_feature_1`~`integer_feature_13`(int32 또는 결측을 포함한 float64), `categorical_feature_1`~`categorical_feature_26`(문자열/object).
- `label`은 검사한 160,000행에서 0 또는 1만 있었고 파싱 실패가 없었다. 양성 수는 날짜 순서대로 1,192, 1,285, 1,341, 1,244건이다. 전체 표본 양성률은 5,062 / 160,000 = **3.16375%**다.
- 결측 셀은 파일별로 155,511 / 1,600,000, 153,547 / 1,600,000, 152,869 / 1,600,000, 156,336 / 1,600,000이다. `integer_feature_4`는 첫 파일의 40,000행 중 17,875행에서 결측이었다.
- 고카디널리티 범주가 실제로 있다. 첫 파일의 40,000행에서 `categorical_feature_20`의 고유값 12,080개, `categorical_feature_1` 11,856개, `categorical_feature_22` 11,405개였다. 이것은 전체 cardinality가 아니다.
- 공식 설명에 따라 13개 수치형, 26개 해시 처리 범주형의 의미는 공개되지 않는다. 라벨은 양성과 음성이 서로 다른 비율로 부분 표본화되어 있어 이 표본의 클릭률을 실제 광고 트래픽의 CTR로 일반화할 수 없다.

## 분할과 자원 계획

각 날짜별 조각의 앞 40,000행만 사용한다. 같은 날짜 안에서 선후를 추론하거나 무작위로 섞지 않는다.

| 구간 | 날짜 경계 | 사용 행 | 클릭 수 |
|---|---|---:|---:|
| train | 2015-02-15, 2015-02-16 | 80,000 | 2,477 |
| calibration | 2015-02-17 | 40,000 | 1,341 |
| test | 2015-02-18 | 40,000 | 1,244 |

`train < calibration < test`이며 날짜가 겹치지 않는다. 모든 전처리의 학습과 기준 모델의 학습은 train만 사용한다. 보정기는 calibration만 사용한다. test는 최종 측정에만 사용한다. Parquet 배치 스트리밍으로 각 조각에서 필요한 40,000행만 읽는다. 결과는 4개 조각의 부분 표본 실험이고 전체 Criteo Click Logs 결과가 아니다.
