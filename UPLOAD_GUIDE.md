# 파일 배치와 배포 안내

## 기존 저장소 루트에 반영할 파일

| 경로 | 처리 |
| --- | --- |
| index.html | 교체 — 채용용 전체 본문 |
| styles.css | 교체 — 콘텐츠 중심 반응형 디자인 |
| app.js | 교체 — 직무 필터·가상 계산기 |
| data.js | 교체 — 단위·PER·위험 계산 예제 |
| projects-library.js | 교체 — 직무 설명. 기존 학습 아이디어 목록 제거 |
| assets/favicon.svg | 추가 |
| package.json | 추가 — 의존성 없는 검사·빌드 명령 |
| scripts/build.mjs | 추가 — 공개 파일만 dist로 복사 |
| tests/finance.test.mjs, tests/content.test.mjs | 추가 — 계산·공개 범위 검사 |
| .github/workflows/deploy.yml | 교체 — 루트 전체 업로드 대신 dist만 배포 |
| .github/workflows/static.yml | 교체 — 중복 배포를 제거하고 PR 사전 검사만 수행 |
| .gitignore | 추가 |
| README.md, UPLOAD_GUIDE.md | 교체 또는 추가 |

외부 npm 패키지가 없어 npm install이 필요하지 않습니다.

## 사용자 직접 반영 시

ZIP 내부 Personal-Portfolio 폴더의 내용을 저장소 루트에 같은 위치로 업로드합니다. 중첩 Personal-Portfolio 폴더를 만들지 않습니다. 숨김 폴더 .github의 배포 파일도 반드시 교체합니다.

Settings → Pages → Source를 GitHub Actions로 지정하고 main에 반영합니다. Actions의 “금융 포트폴리오 배포” 성공 후 https://sth00619.github.io/Personal-Portfolio/ 에서 확인합니다.

## 공개 범위

PORTFOLIO_REVAMP_BRIEF.md는 설계 참고자료로만 남겨두며 이번 변경 커밋·배포 묶음에 포함하지 않습니다. 원본 데이터, 프롬프트, 내부 구조 문서, 개인 계좌, 공급자 요청 로그도 포함하지 않습니다. 이미지 원본을 공개 결과물로 확인할 수 없어 사용하지 않았으며, 그 대신 일반 금융 수식과 가상 예제를 사용합니다.

이전 전달물의 public/evidence 폴더나 전체 개발 문서는 이번 사이트에 합치지 않습니다.

## 본문 추가

index.html의 프로젝트 상세와 소개 부분을 편집합니다. 개인별 실제 담당 모듈·재학 정보·연락처를 확정하면 해당 문구만 추가하면 됩니다. 별도 브라우저 저장에 의존하지 않아 방문자 모두 같은 본문을 읽습니다.

## 배포 검증

npm test → npm run build 순서로 실행합니다. dist에는 index.html, styles.css, app.js, data.js, projects-library.js, assets/favicon.svg의 6개 파일만 존재해야 합니다. 본문은 JavaScript를 꺼도 읽을 수 있습니다.

2026-09-07 시각화 추가: 루트의 `index.html`, `styles.css`, `app.js`, `studio.js`, `scripts/build.mjs`, `tests/content.test.mjs`와 `assets/image-review.jpg`를 함께 반영하세요. 현재 GitHub Actions 빌드는 이 이미지와 모듈만 추가 허용합니다. 설명 문서와 내부 브리프는 공개 사이트에 배포하지 않습니다.
