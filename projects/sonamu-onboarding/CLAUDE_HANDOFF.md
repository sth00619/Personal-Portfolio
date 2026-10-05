# Sonamu 포트폴리오 전달 요약

GitHub 브랜치 `codex/sonamu-onboarding`이 `main`에 병합된 뒤, 기존 Portfolio Hub에 이 사례를 **별도의 준비 실습**으로 연결한다. 공개 문구는 저장소 `CLAUDE.md`의 문서 규칙을 적용한다.

## 권장 서사

1. **평가 유형:** [CartaNova Engineer 공고](https://cartanova.notion.site/CartaNova-2-Engineer-3d5f753e4fb98123bd4fc56bbd32cc37)는 Sonamu 기반 과제, 에이전트 세션 기록, 짧은 판단 리포트를 요구한다.
2. **준비 질문:** 공식 Miomock 예제의 컨테이너가 준비됐더라도 앱이 같은 DB에 연결했는지 어떻게 확인할까?
3. **실패와 반증:** 첫 마이그레이션은 연결 풀 타임아웃. 컨테이너 내부 DB는 정상이나 호스트 `127.0.0.1:5432`는 다른 PostgreSQL을 가리켰다. Node `pg`는 `role "postgres" does not exist`를 반환했다. 근거는 [`SESSION_REVIEW.md`](SESSION_REVIEW.md).
4. **수정과 결과:** 기존 로컬 DB는 유지하고 예제 DB만 `15432`로 재매핑. 개발 DB 마이그레이션, 테이블 21개, 관리자 화면·Sonamu UI·API 3경로 HTTP 200을 확인했다. 근거는 [`compose.port-override.yml`](compose.port-override.yml), [`smoke_miomock.py`](scripts/smoke_miomock.py), [`local_smoke.json`](results/local_smoke.json).
5. **깨달음:** 컨테이너 준비 상태와 호스트 연결 대상은 다른 검증 문제다. 에이전트가 제안한 오류 원인은 포트 점유·실제 SQL 오류·후속 HTTP 응답으로 판정해야 한다.

## 표현 경계

- 공식 Miomock 애플리케이션의 기능 구현은 CartaNova의 작업이다. 포트 오버라이드·점검 스크립트·판단 기록만 이 포트폴리오에서 작성했다.
- 이 문서는 실제 채용 과제를 수행했다는 주장이 아니다. [`INTERVIEW_REPORT_TEMPLATE.md`](INTERVIEW_REPORT_TEMPLATE.md)는 실제 과제에서 원본 세션과 별도로 사용할 빈 틀이다.
- 사용자는 준비 목표와 공고 링크를 제공했다. 조사·진단·구현·측정은 Codex가 수행했다.
- 로컬 포트 충돌은 이 컴퓨터에서 관찰된 환경 조건이며 Sonamu 프레임워크의 일반적 결함으로 서술하지 않는다.

Notion 본문에는 문제 → 실패한 가설 → 반증 증거 → 수정 → 실행 결과 → 다음 실험의 흐름을 사용하고, 결과 주장은 위 GitHub 파일에 연결한다. GitHub 루트 README에는 이미 사례 요약이 있으므로 수치와 경계를 확인해 유지한다.
