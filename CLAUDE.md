# CLAUDE.md — Personal-Portfolio

> Codex는 모든 채팅 세션 시작 시 이 파일을 자동으로 읽습니다.
> 이 파일의 규칙은 WO-01, WO-02 등 모든 작업지시서 실행에 공통으로 적용됩니다.

---

## 프로젝트 정체

- **오너**: Song Tae-ho (SONG) — SeoulTech 산업공학·ITM 4학년
- **목적**: 데이터/AI·ML 직군 취업용 포트폴리오 프로젝트 구현
- **레포**: https://github.com/sth00619/Personal-Portfolio
- **사이트**: https://sth00619.github.io/Personal-Portfolio/
- **Notion Hub**: https://app.notion.com/p/3df76d2e4c1c80b1b168db16c30a457d

---

## 기술 스택 (공통)

- **언어**: Python 3.11 (ML·데이터), Java/Spring Boot (백엔드 API, SONG 기존 경험)
- **패키지 관리**: pip (Python), Maven (Java)
- **컨테이너**: Docker Compose — 모든 프로젝트 컨테이너화 원칙
- **DB**: PostgreSQL 16 (PostGIS, TimescaleDB), Redis
- **테스트**: pytest (Python), JUnit (Java)
- **CI**: GitHub Actions

---

## 폴더 구조 규칙

```
Personal-Portfolio/
├── CLAUDE.md                  ← 이 파일 (건드리지 말 것)
├── projects/
│   ├── wo-01-retrieval-eval/  ← WO-01 작업 폴더
│   │   ├── README.md          ← 반드시 작성
│   │   ├── src/
│   │   ├── tests/
│   │   └── data/              ← 원본 데이터 커밋 금지, 다운로드 스크립트만
│   ├── wo-02-hybrid-rag/
│   └── ...
└── docs/
    └── codex-workorders/      ← 작업지시서 원본 (읽기 전용)
```

- 각 WO는 독립 폴더. 다른 WO 폴더를 수정하지 말 것.
- `data/` 폴더에 원본 데이터 파일 커밋 금지. `data/download.sh` 또는 `data/README.md`에 다운로드 방법만 기록.
- 대용량 파일(.pkl, .bin, .h5, .parquet)은 `.gitignore`에 추가.

---

## 커밋 메시지 규칙

```
[WO-번호] 타입: 내용
```

타입: `feat` `fix` `docs` `test` `refactor` `data` `chore`

예시:
```
[WO-01] feat: add BM25 + dense hybrid retriever
[WO-01] test: add CI regression gate for recall@10
[WO-02] docs: add results table to README
```

- 커밋 단위는 작게. 기능 하나당 커밋 하나.
- 작업 완료 후 반드시 `[WO-번호] docs: update README with results` 커밋 포함.

---

## README.md 필수 구조 (모든 WO 공통)

각 `projects/wo-XX/README.md`는 아래 섹션을 반드시 포함합니다.

```markdown
# WO-XX · [프로젝트명]
> 개인 프로젝트 · 대응 직군: [직군] · 데이터: [출처·라이선스]

## 문제 정의
## 가설
## 데이터
## 접근 / 파이프라인
## 결과 (Ship Gate 표)
| 지표 | 목표 | 실제 |
|------|------|------|

## 시행착오와 해결
## 한계
## 개발 방식 (AI 활용 구분)
| 직접 작성한 것 | Codex가 생성한 것 |
|---|---|

## 관련 개념
## English Technical Summary
```

---

## 코드 품질 규칙

- **타입 힌트 필수** (Python): 모든 함수에 `def fn(x: int) -> str:` 형태
- **독스트링 필수**: 함수마다 1줄 이상
- **매직 넘버 금지**: 상수는 파일 상단에 `CONSTANT_NAME = value` 로 정의
- **하드코딩 경로 금지**: 경로는 `pathlib.Path` 또는 환경변수로
- **시크릿 하드코딩 절대 금지**: API 키, 비밀번호는 `.env` + `python-dotenv`. `.env`는 `.gitignore`에 포함

---

## Ship Gate 원칙

- 각 WO의 작업지시서(⑥ Ship Gate)에 명시된 정량 기준을 **전부** 충족해야 완료
- "그럴듯해 보인다"는 완료가 아님. 숫자가 있어야 완료.
- CI 게이트가 명시된 WO는 `tests/test_regression.py`를 만들고 실제로 실패하는 케이스를 시연할 것

---

## 병렬 작업 규칙 (여러 WO를 동시에 실행할 때)

- 각 Codex 채팅은 **자신의 WO 폴더만** 수정합니다.
- 공통 유틸(`utils/`)이 필요하면, 먼저 만드는 쪽이 `utils/` 폴더에 작성하고 커밋. 나머지는 그걸 import.
- 다른 WO 폴더나 `CLAUDE.md`는 절대 수정하지 말 것.
- 충돌 방지: 브랜치 전략은 `dev/wo-01`, `dev/wo-02` 처럼 WO별 브랜치 사용.

---

## SONG에게 넘길 산출물 체크리스트

각 WO 완료 시 아래가 준비되어 있어야 합니다.

- [ ] `projects/wo-XX/README.md` — Ship Gate 결과 표 포함
- [ ] `projects/wo-XX/src/` — 실행 가능한 코드
- [ ] `projects/wo-XX/tests/` — 최소 Ship Gate 검증 테스트
- [ ] `projects/wo-XX/data/download.sh` 또는 설명
- [ ] 커밋 히스토리 — 의미 있는 단위로 나뉘어 있음

SONG이 이것들을 Claude(claude.ai)에게 넘기면, Claude가:
1. GitHub README를 최종 정리
2. Notion Portfolio Hub에 결과·면접 대비·트러블슈팅을 직접 기록

---

## 하지 말아야 할 것 (Do Not)

- `data/` 에 원본 데이터 파일 커밋
- `.env` 파일 커밋
- `CLAUDE.md` 수정
- 다른 WO 폴더 수정
- Ship Gate 숫자 없이 완료 선언
- `main` 브랜치에 직접 커밋 (반드시 `dev/wo-XX` 브랜치 사용)
