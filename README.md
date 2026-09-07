# 송태호 · 금융 개발 포트폴리오

공개 사이트: https://sth00619.github.io/Personal-Portfolio/

금융 데이터 전처리, 수식의 전제, 프로젝트에서 확인한 작업과 검증 범위를 소개합니다. 개인 학습 트래커를 채용 담당자가 바로 읽을 수 있는 정적 콘텐츠로 개편했습니다.

## 편집 위치

- index.html: 자기소개, 프로젝트 경험, 전처리 설명, 금융 개념, 협업과 지원 방향
- styles.css: 반응형 스타일과 인쇄 표시
- data.js: 공개용 가상 계산 예제. 운영 코드와 분리
- projects-library.js: 관심 직무별 설명 문구
- app.js: 직무 필터·가상 계산기·인쇄
- assets/favicon.svg: 아이콘
- scripts/build.mjs: 공개 파일 허용 목록
- .github/workflows/deploy.yml: 검사 후 GitHub Pages 배포

## 로컬 실행과 검사

Node.js 22 및 Python 3을 사용합니다. 외부 npm 의존성과 API 키가 필요하지 않습니다.

```sh
npm test
npm run build
npm run dev
```

http://127.0.0.1:5174 에서 확인합니다. 주요 글은 HTML에 포함되어 있어 JavaScript 없이도 읽을 수 있습니다. 페이지 내부 링크와 상대 자산 경로를 사용하므로 GitHub Pages의 저장소 경로에서 작동합니다.

## 공개 범위

내부 브리프, 프로젝트 전체 소스, 원본 금융 데이터, 상세 아키텍처, 운영 로그·프롬프트·비용 정책은 배포하지 않습니다. 빌드는 명시적으로 허용한 파일만 dist에 복사합니다. 공개 저장소에 커밋하는 파일 자체도 공개되므로 내부 자료는 커밋하지 않습니다.

계산기는 일반적인 수식을 설명하는 가상 예제입니다. 투자 실적이나 실제 시장 정보가 아닙니다. FinanceManus/FinanceX는 협업의 구조·이론 검토와 UI/UX·문서화 범위로 소개하며 금융 엔진 전체를 개인 구현으로 표현하지 않습니다.

미확인 학력·근무 경력·개인 기여율·수익률은 추가하지 않았습니다. 확정 정보는 index.html의 소개 영역에 추가합니다.

## 업로드와 배포

UPLOAD_GUIDE.md를 참고하세요. GitHub Pages의 Source는 GitHub Actions를 사용합니다.
