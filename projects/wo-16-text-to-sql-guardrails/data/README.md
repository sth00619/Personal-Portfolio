# 평가 데이터 다운로드

원본 벤치마크와 SQLite DB는 저장소에 커밋하지 않습니다. 프로젝트 루트에서 다음 명령을 실행하면 BIRD Mini-Dev 질문 파일과 DB 묶음을 `data/`에 받습니다.

```bash
python3.11 download_data.py
```

- 질문: [BIRD Mini-Dev Hugging Face 데이터셋](https://huggingface.co/datasets/birdsql/bird_mini_dev), revision `f65faf4ae3b638c1fa6df1d3370c8d92c8366301`
- SQLite DB 묶음: [BIRD 공식 Mini-Dev 아카이브](https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip)
- 체크섬: 프로젝트의 `download_data.py`가 고정 SHA-256과 다른 파일을 거부합니다.
- 라이선스: Hugging Face 데이터 카드의 CC BY-SA 4.0 표기와 BIRD 프로젝트의 이용 조건을 확인하고 출처를 표시하세요.

내려받은 모든 데이터·DB 파일은 이 폴더의 `.gitignore`에 따라 추적하지 않습니다. 내려받기 스크립트는 출처와 SHA-256을 `docs/source_manifest.json`에 기록합니다.
