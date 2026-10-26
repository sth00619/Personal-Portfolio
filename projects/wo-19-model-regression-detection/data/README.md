# 골든셋 입력

WO-19은 새 레이블을 만들지 않는다. WO-07에서 검증한 Avazu 시간 분할과 평가 표본을 재사용한다. `compose.yaml`은 `../wo-07-ctr-calibration/data/avazu_sample.csv.gz`를 읽기 전용으로 연결하며, 원본 Kaggle 압축 파일이나 파생 행 단위 예측을 이 폴더에 복사하지 않는다.

재현 전에 WO-07에서 `avazu_sample.csv.gz`를 준비해야 한다. 없으면 저장소 루트에서 다음을 실행한다.

```bash
cd projects/wo-07-ctr-calibration
docker compose run --build --rm avazu
```

표본 생성은 기존 WO-07의 SHA-256·스키마·행 수·날짜 순서 감사와 `crc32(id) % 40 == 17` 고정 추출 규칙을 따른다. 해당 표본의 마지막 두 날짜만 WO-19의 홀드아웃 평가에 사용한다. 파일은 WO-07 `.gitignore`에 따라 Git에서 제외된다.
