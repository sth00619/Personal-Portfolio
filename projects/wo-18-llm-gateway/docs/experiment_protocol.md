# WO-18 실험 프로토콜

## 구성

- 애플리케이션: Spring Boot 3.5.16, Java 21 컨테이너
- 제공자: 정상 primary, 정상 backup, 600ms 지연 모드 slow를 실행하는 별도 mock 서버 3개
- 속도 제한 저장소: Redis 7.4, Lua 스크립트에서 Redis 서버 시각으로 원자적 토큰 갱신
- 토큰 버킷: 초기 용량 5 tokens, refill 5 tokens/second
- 제공자 호출 timeout: connect/read 각 250ms
- 재시도: 제공자별 최대 2회 호출
- 서킷 브레이커: 연속 3회 오류 후 OPEN, 2,000ms 차단, 요청 1개 HALF_OPEN probe
- 대기 정책: 토큰이 생길 때까지 요청 thread가 대기하며 1,200ms 경과 시 HTTP 429

## 장애 전환

1. 통계를 초기화하고 primary를 `FAIL_ALL`로 설정한다.
2. 동일한 bucket key로 요청 6건을 순차 제출한다.
3. 최초 요청 시작부터 backup 응답을 받을 때까지를 최초 failover latency로 기록한다.
4. 6건의 HTTP 결과와 게이트웨이의 최종 실패 카운터를 확인한다.
5. primary를 정상 모드로 복귀시킨 뒤, 회로가 열린 동안의 라우팅과 2,000ms cooldown 이후 HALF_OPEN 복구를 관측한다.

유실 요청은 primary 시도 수가 아니라 **모든 제공자 시도 뒤에도 클라이언트에 성공 응답을 주지 못한 게이트웨이 요청 수**로 정의한다.

## 속도 제한

- 정책마다 서로 다른 API key를 사용해 Redis bucket을 새로 시작한다.
- 각 정책 실험은 20개 요청을 동시에 제출하고 3회 반복한다.
- REJECT는 토큰이 없을 때 즉시 HTTP 429를 반환한다.
- QUEUE는 요청별 ticket을 Redis FIFO 목록에 넣고, head 요청만 token을 받을 수 있게 Lua에서 queue head 확인과 token 차감을 원자적으로 처리한다. HTTP request thread는 최대 1,200ms까지 기다린다.
- p95는 성공과 429를 모두 포함한 20개 응답 지연의 nearest-rank percentile이다.
- 성공 처리량은 한 burst에서 성공 응답 수를 burst 시작부터 마지막 응답 완료까지의 wall time으로 나눈 값이다. 짧은 burst 결과이며 지속 처리량으로 일반화하지 않는다.
- README에는 3회 반복한 성공 건수·p95·성공 처리량의 중앙값을 보고한다.

## 사용량 및 합성 비용

- prompt token: prompt 문자열 길이의 `ceil(문자 수 / 4)`, 최소 1
- completion token: mock 응답마다 16
- 합성 가격: prompt token당 2 micro-USD, completion token당 8 micro-USD
- 정상 실행 4건의 게이트웨이 합계와 각 제공자 사용량을 비교한다.
- 다음에는 slow 제공자를 첫 번째로 배치하고 600ms 생성 지연과 250ms 게이트웨이 timeout을 적용한다. 게이트웨이 요청이 timeout된 뒤에도 서버 작업은 계속되어 제공자 집계에 남을 수 있다.
- timeout 실험의 정확도는 실험 전 정상 실행값을 뺀 증가분으로 계산한다: `1 - |provider cost delta - gateway cost delta| / provider cost delta`.

## 재현

프로젝트 디렉터리에서:

```bash
docker compose up --build -d
python3 scripts/run_experiments.py
docker compose down
```

원시 API key 문자열은 Redis 키로 저장하지 않는다. Redis에는 SHA-256으로 변환된 bucket·queue 식별자만 남는다.
