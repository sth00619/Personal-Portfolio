# WO-22 데이터 준비

SQuAD 2.0 공식 dev JSON은 `python data/download.py`로 받습니다. 스크립트는 공식 URL, 파일 크기, SHA-256을 검증합니다. 원본 데이터는 Git에서 제외합니다.

WO-22는 WO-20의 기존 A/B 모델 응답을 사용하므로 추가 API 호출이 없습니다. `projects/wo-20-prompt-ab-platform/results/predictions.jsonl`을 `projects/wo-22-llm-cost-autopilot/data/model_predictions.jsonl`에 복사하면 됩니다. 응답 기록은 Git에서 제외됩니다. 새 복제 환경에서 응답 파일을 만들려면 WO-20 실험을 실행해야 하며, 그때는 WO-20의 API 설정과 비용 상한을 따릅니다.

```bash
cp ../wo-20-prompt-ab-platform/results/predictions.jsonl data/model_predictions.jsonl
```

SQuAD는 [Stanford SQuAD 페이지](https://rajpurkar.github.io/SQuAD-explorer/)의 CC BY-SA 4.0 데이터셋입니다.
