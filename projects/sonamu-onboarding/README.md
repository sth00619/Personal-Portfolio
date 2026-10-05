# Sonamu · 예제 환경 진단과 에이전트 검증 기록

> 개인 준비 실습 · 대응 직군: Software Engineer · 기반: [Sonamu 공식 저장소의 Miomock 예제](https://github.com/cartanova-ai/sonamu/tree/master/examples/miomock)

## 문제 정의

[CartaNova Engineer 전형 안내](https://cartanova.notion.site/CartaNova-2-Engineer-3d5f753e4fb98123bd4fc56bbd32cc37)는 낯선 Sonamu 과제를 에이전트와 함께 다루면서 **에이전트의 결과를 판정·수정한 과정**을 평가한다고 설명한다. 이를 준비하기 위해 [공식 설치 문서](https://sonamu.cartanova.ai/ko/getting-started/installation)와 [빠른 시작](https://sonamu.cartanova.ai/ko/getting-started/quick-start)을 읽고, 공식 `examples/miomock`의 빌드·DB·화면·API가 로컬에서 실제로 연결되는지 검증했다.

## 가설

Docker 컨테이너가 실행 중이어도 애플리케이션이 **의도한 PostgreSQL**에 연결된다고 단정할 수 없다. 호스트 포트 충돌을 분리하고 DB 마이그레이션과 HTTP 응답까지 확인하면, 환경 오류와 코드 오류를 구분할 수 있다.

## 접근 — 시도 순서

1. 공식 저장소의 고정 커밋을 클론하고 `mise`가 지정한 Node.js·pnpm으로 의존성을 설치한 뒤 모노레포 빌드를 통과했다.
2. 예제 Compose로 PostgreSQL 18 컨테이너를 띄웠다. 컨테이너 내부의 연결 확인은 통과했지만 개발 DB 마이그레이션은 `Knex: Timeout acquiring a connection`으로 실패했다.
3. 호스트 `127.0.0.1:5432`에 접속한 Node `pg`가 `role "postgres" does not exist`를 반환했다. `lsof`에는 기존 로컬 PostgreSQL과 Docker 프록시가 함께 나타났다. 컨테이너 내부에는 `postgres` 역할과 `miomock_development` DB가 있어 호스트의 접속 대상이 다르다고 판정했다.
4. [Compose 포트 오버라이드](compose.port-override.yml)로 **예제 DB만** `127.0.0.1:15432`에 공개하고 `SONAMU_DB_HOST`·`SONAMU_DB_PORT`를 명시했다. 직접 DB 연결과 마이그레이션이 통과했다.
5. 개발 서버를 실행하고 관리자 화면·Sonamu UI·API를 브라우저 및 [자동 점검 스크립트](scripts/smoke_miomock.py)로 확인했다. 에이전트의 가설과 반증 과정은 [판단 기록](SESSION_REVIEW.md)에 남겼다.

## 결과 (검증 표)

| 검증 항목 | 결과 | 근거 |
|---|---:|---|
| 고정 업스트림 커밋 모노레포 빌드 | 통과 | 로컬 `mise run build` |
| 개발 DB 마이그레이션 | 통과 | 로컬 Sonamu CLI 출력 |
| 개발 DB `public` 테이블 | 21개 | 컨테이너 내부 SQL 조회 |
| `/admin` · `/sonamu-ui` · `/api/user/getMyIP` | HTTP 200 · 200 · 200 | [점검 결과 JSON](results/local_smoke.json) |
| 브라우저 렌더링 | 관리자 대시보드와 Sonamu UI 확인 | 로컬 브라우저 확인 |

**측정 방식**: 고정 업스트림 커밋의 로컬 예제에서 PostgreSQL과 HTTP 경로를 실행해 점검했다. [점검 스크립트](scripts/smoke_miomock.py)는 Docker 공개 포트, 개발 DB 테이블, 세 HTTP 경로와 API 응답 형태를 확인한다.

## 시행착오와 의사결정

첫 실패 메시지의 “connection pool”만 보고 트랜잭션 코드를 수정하면 잘못된 대상에 손댈 수 있었다. 컨테이너 안 DB는 정상이었고, 호스트 주소에서 받은 PostgreSQL 오류가 달랐다. 따라서 애플리케이션이 **어느 리스너로 접속하는지**를 확인한 뒤, 기존 로컬 DB를 중단하는 대신 예제 컨테이너의 공개 포트만 변경했다. 마이그레이션 성공 후에도 화면과 API를 요청해 수정이 전체 경로에서 유효한지 확인했다.

## 재현

Sonamu 공식 저장소를 클론하고 [기록된 커밋](results/local_smoke.json)을 체크아웃한다. `mise`, Docker Compose가 필요하다. 아래 경로 변수는 각자의 절대 경로로 설정한다.

```bash
SONAMU_REPO=/absolute/path/to/sonamu
PORTFOLIO_REPO=/absolute/path/to/Personal-Portfolio
cd "$SONAMU_REPO"
git checkout 968acc7da5843a234d471ca2d4c0ad5d905e63d7
mise trust
mise install --locked
SKIP_LEFTHOOK=1 mise exec -- pnpm install --frozen-lockfile
mise run build
cd "$SONAMU_REPO/examples/miomock/api"
docker compose -f database/docker-compose.yml -f "$PORTFOLIO_REPO/projects/sonamu-onboarding/compose.port-override.yml" up -d
SONAMU_DB_HOST=127.0.0.1 SONAMU_DB_PORT=15432 mise exec -- pnpm sonamu migrate apply development --execute --confirm
SONAMU_DB_HOST=127.0.0.1 SONAMU_DB_PORT=15432 mise exec -- pnpm dev
```

개발 서버가 준비됐으면 다른 터미널에서 점검한다.

```bash
python3 "$PORTFOLIO_REPO/projects/sonamu-onboarding/scripts/smoke_miomock.py" \
  --upstream "$SONAMU_REPO" \
  --output "$PORTFOLIO_REPO/projects/sonamu-onboarding/results/local_smoke.json"
```

## 측정 경계 (한계)

이 기록은 **공개 예제의 로컬 온보딩과 환경 진단**이다. 업스트림 예제의 기능 구현을 본인 성과로 계산하지 않는다. 자동 점검은 빌드·화면·API의 기본 경로를 다루며, 전체 테스트 스위트나 실제 채용 과제를 대신하지 않는다. **다음 단계:** 과제가 제공되면 실제 요구사항으로 기능·회귀 테스트를 구현하고 원본 에이전트 세션 기록과 판단 리포트를 별도로 제출한다.

## 개발 방식 (AI 활용 구분)

| 사용자 제공 | Codex 수행 |
|---|---|
| Sonamu 예제 실행·포트폴리오 반영 목표와 채용 공고 링크 | 공식 자료 조사, 예제 빌드·실행, 포트 충돌 진단, Compose 오버라이드·점검 스크립트·판단 기록 작성 |

## 관련 개념

**컨테이너 준비 상태**는 컨테이너 내부의 서비스 상태이고, **호스트 공개 포트**는 애플리케이션의 접속 경로다. 같은 숫자의 포트에 서로 다른 리스너가 보일 수 있으므로, DB 내부·호스트 TCP·애플리케이션 응답을 함께 확인해야 한다.

## English Technical Summary

I ran CartaNova's public Miomock example at a pinned Sonamu commit and investigated a failed database migration. The container was healthy, but a separate PostgreSQL process occupied the host loopback port. I remapped only the example container, applied development migrations, and verified 21 public tables plus three HTTP routes. The original contribution here is a reproducible port override, smoke check, and decision log; the upstream example remains CartaNova's work.
