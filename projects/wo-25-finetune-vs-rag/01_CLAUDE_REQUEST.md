# Claude 요청문 — WO-25 GitHub·Notion 정리

첨부한 `WO-25-finetune-vs-rag` 프로젝트 자료와 `CLAUDE_HANDOFF.md`의 근거 장부·판단 장면을 확인해 GitHub와 기존 Notion WO-25 페이지를 정리해 주세요.

## 반영할 자료

- `README.md`: 프로젝트 설명, 실제 실험 설정과 결과, 한계
- `results/source_manifest.json`: 고정 데이터·모델 revision, 라이선스, split 규모와 파일 해시
- `results/lora_sweep_runs.json`: LoRA rank·학습 예제 수 비교와 선택 근거
- `results/prompt_validation_sweeps.json`: few-shot 수와 RAG top-k validation 비교
- `results/gsm8k_summary.json`: 동일 GSM8K official test 전체의 네 경로별 분자·분모·정확도
- `results/mmlu_summary.json`: MMLU base/LoRA 정확도 및 percentage-point 차이
- `results/gsm8k_analysis.json`: all-wrong, RAG-only, LoRA-only 실제 문항·생성 답변·검색 예제 근거
- `results/interpretation.md`: 분자/분모 기반 해석, 각 사례군 3건의 실제 근거와 한계
- `CLAUDE_HANDOFF.md`: 작업 중 실제로 일어난 판단·시행착오와 결과 해석의 근거

## 업데이트 요청

1. 저장소 루트 README의 WO-25 항목/요약을 실측 결과로 갱신해 주세요. WO-20은 같은 모델에서 프롬프트 두 버전을 비교했고, WO-25는 같은 베이스에서 zero-shot/few-shot/RAG/LoRA 적용 방법을 비교했다는 차이를 한 줄로 밝혀 주세요.
2. 기존 Notion WO-25 케이스 스터디 페이지를 실험 설계, 전체 test 결과, validation 하이퍼파라미터 비교, MMLU %p 변화, 실패 사례 분석 순서로 정리해 주세요.
3. README와 Notion에 정확한 분자/분모를 표기하고, 정확도는 `정답 수 ÷ 전체 수 × 100`, MMLU 차이는 percentage point(%p)로 표현해 주세요. 값은 JSON 결과 파일과 일치시켜 주세요.
4. `CLAUDE_HANDOFF.md`의 판단 장면을 토대로 첫 시도 → 관측/한계 → 바꾼 결정 → 근거 순서로 간결하게 서술해 주세요. 선택하지 않은 rank, 학습 예제 수, few-shot 수, RAG top-k도 validation 수치와 함께 남겨 주세요.
5. `results/gsm8k_analysis.json`의 실제 세 사례군을 각 최소 3건씩 설명해 주세요. 요약 근거는 `results/interpretation.md`, 원문 출력은 `results/gsm8k_analysis.json`에서 확인해 주세요. 원문 출력과 검색 예제를 근거로 삼고, 데이터가 뒷받침하지 않는 실패 원인을 상상해 쓰지 말아 주세요. 한 사례군이 3건 미만이면 있는 수만 보고하고 Ship Gate 미충족 사실을 밝혀 주세요.
6. 측정되지 않은 주장이나 중간 진행률을 최종 성능처럼 쓰지 말아 주세요. MMLU의 100문항·10개 과목 표본, 단일 seed, 단일 소형 모델이라는 경계를 분명히 해 주세요.
7. 저장소의 `CLAUDE.md` 문서화 규칙을 적용해 주세요. 용어집은 README에서 English Technical Summary 바로 앞, Notion에서는 관련 링크 바로 앞에 두고, 시간 표현을 넣지 말아 주세요.

이 전달 패키지에는 모델 가중치와 원본/가공 benchmark 데이터가 들어 있지 않습니다. 집계 결과와 대표 사례는 첨부 결과 파일을 사용해 주세요. 결과 파일이 비어 있거나 없으면 추측하지 말고 작업을 멈춘 뒤 그 사실을 알려 주세요.
