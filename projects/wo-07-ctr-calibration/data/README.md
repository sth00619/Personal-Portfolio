# 데이터 다운로드

`bash data/download.sh`는 Criteo 공식 [Click Logs 배포처](https://huggingface.co/datasets/criteo/CriteoClickLogs)의 날짜별 Parquet 파일에서 각 날짜에 대해 고정된 파일 하나씩 받는다. 원본은 Git에 포함하지 않는다.

라이선스는 [CC BY-NC-SA 4.0](https://huggingface.co/datasets/criteo/CriteoClickLogs/blob/main/README.md)이다. 연구·비상업 목적에서 출처와 라이선스를 표시한다. 원본 데이터는 이 프로젝트의 `data/` 디렉터리에서만 보관한다.

## Avazu 독립 검증

[Kaggle Avazu CTR Prediction](https://www.kaggle.com/competitions/avazu-ctr-prediction/data)의 `train.gz`를 본인이 대회 페이지에서 받은 뒤 이 폴더에 `avazu_train.gz`라는 이름으로 복사한다. 원본과 추출 표본은 `.gitignore`에 따라 Git에서 제외한다. 대회 데이터의 이용 조건은 [Competition Rules](https://www.kaggle.com/competitions/avazu-ctr-prediction/rules)를 확인한다.

`docker compose run --build --rm avazu`는 원본의 SHA-256, 전체 행의 클릭·시간 순서, 10개 날짜를 검증한다. `crc32(id) % 40 == 17`인 행만 선택하여 `avazu_sample.csv.gz`를 만들고, 학습·보정·평가 기간을 분리한다. 분석 결과는 `results/avazu/`에만 저장한다. Criteo와 Avazu는 서로 다른 데이터셋이므로 점수를 직접 비교하지 않는다.
