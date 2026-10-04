# 데이터 준비

`docker compose run --build --rm download`는 [ZOZO Research의 Open Bandit Dataset](https://research.zozo.com/data.html) 전체 ZIP에서 Men 캠페인의 Uniform Random 로그, Bernoulli TS 로그, 아이템 문맥 파일만 추출한다. 압축 멤버의 원본 ZIP CRC와 크기를 확인한다. `data/raw/`는 Git에서 제외한다.

Random 로그로 모델을 학습하고 다른 Random 관측치를 OPE에 사용한다. 별도 Bernoulli TS 로그의 실제 평균 클릭을 관측 정책값으로 계산한다. 소형 샘플 대신 캠페인의 전체 로그를 사용한다. 데이터셋의 [CC BY 4.0 표기](https://huggingface.co/datasets/zozonext/open-bandit)와 원 배포처의 이용 안내를 확인하고 원본을 재배포하지 않는다.
