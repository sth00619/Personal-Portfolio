# Criteo Uplift Prediction Dataset v2.1

공식 출처: [Criteo AI Lab 데이터 설명](https://ailab.criteo.com/criteo-uplift-prediction-dataset/). 해당 페이지의 erratum은 초기 버전의 누출 문제를 설명하고 수정본 v2.1 다운로드를 제공한다. 라이선스는 CC BY-NC-SA 4.0이다.

```bash
python3 data/download.py
```

수정본의 다운로드 URL과 파일 크기는 `download.py`에 고정한다. 원본 `csv.gz`는 Git에 포함하지 않는다. 실험은 원본 전체의 기본 수치를 감사하고, 행 순서와 라벨을 사용하지 않는 난수 표본으로 일부만 학습한다. `treatment`는 무작위 배정 변수이며 `exposure`는 그 뒤에 관측되는 실제 노출 변수이므로 학습 피처와 처치 정의에서 제외한다.
