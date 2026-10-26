# WO-18 · LLM 게이트웨이 (Large Language Model Gateway)

> 개인 프로젝트 · 대응 직군: AI (Artificial Intelligence) 백엔드 · 기술: Java/Spring Boot, Redis · 데이터: 결정적 합성 제공자 응답

## 문제 정의

여러 대규모 언어 모델(Large Language Model, LLM) 제공자를 연결하면 주 제공자의 응답 시간 초과(timeout)·서버 오류(HTTP 5xx)에서 보조 제공자(backup provider)로 전환하는 장애조치(failover), 호출량 제한(rate limiting), 제공자별 토큰 사용량과 합성 비용 기록이 필요합니다. 이 프로젝트는 외부 API 키와 과금 없이 제어 가능한 모의(mock) 제공자 3개를 구성하고, 백엔드 게이트웨이의 장애·혼잡·사용량 경계를 측정합니다.

## 가설

- 주 제공자의 연속 실패를 서킷 브레이커(circuit breaker)로 감지하고 backup 제공자로 보내면, 클라이언트 오류 수와 복구 시점을 실측할 수 있습니다.
- 토큰 버킷(token bucket) 제한에 즉시 거부와 제한 시간 대기를 적용하면, 버스트에서 성공 처리 건수와 95th-percentile latency(p95)의 차이가 드러납니다.
- 정상 응답에서 게이트웨이 사용량과 mock 제공자 사용량은 일치하더라도, 응답 timeout은 제공자 작업을 취소하지 못해 비용 집계 차이를 만들 수 있습니다.

## 접근 — 시도 순서

1. **Spring Boot 선택**: WO 지침의 Spring Boot/FastAPI 선택지에서 SONG의 Spring 백엔드 경력과 직접 연결되는 Spring Boot를 택했습니다. 외부 모델 API 대신 정상·실패·지연 동작을 제어하는 제공자 프로세스 3개를 만듭니다.
2. **실패 전환 구현**: primary를 `FAIL_ALL`로 설정하고 제공자별 최대 2회 호출, 연속 3회 실패 차단, 2,000ms cooldown 뒤 HALF_OPEN probe를 관측합니다. 첫 시도에서는 timeout이 `RestClientException`의 변환 예외로 포장되어 예외 처리 경로를 벗어나 HTTP 500이 났습니다. 원인 로그에서 `SocketTimeoutException`을 확인한 뒤 제공자 호출 예외를 재시도·차단·다음 제공자 경로에 연결했습니다.
3. **제한 정책 비교**: Redis Lua 토큰 버킷(token bucket)의 초기 용량을 5, refill을 초당 5 tokens로 고정하고 동시 요청 20건을 정책마다 3회 보냅니다. FIFO(First-In, First-Out) 대기 정책은 Redis 목록에 요청 ticket을 넣고 HTTP 요청 thread에서 최대 1,200ms 기다립니다.
4. **사용량 경계 확인**: 정상 응답 4건에서 제공자 집계와 gateway 집계를 먼저 비교합니다. 이어 slow 제공자를 앞세워 응답은 timeout되지만 mock 생성 작업은 완료되는 상황을 만들고, 실험 전후 비용 증가분을 대조합니다.

## 데이터

외부 학습 데이터셋은 사용하지 않습니다. mock 제공자는 입력 문자열 길이로 prompt token을 결정하고 응답당 16 completion tokens를 기록합니다. 입력은 `ceil(문자 수 / 4)` tokens, 최소 1 token이며, 합성 비용은 입력 token당 2 micro-USD와 출력 token당 8 micro-USD입니다. 이는 결정적 사용량 회계를 실험하기 위한 프로젝트 내부 값입니다.

## 파이프라인

`HTTP 요청 → X-API-Key별 SHA-256 bucket 식별자 → Redis Lua 토큰 버킷 → 우선순위 제공자 호출·재시도 → 서킷 브레이커 → 사용량 집계 → JSON 응답`

운영 제어 API는 제공자 모드, 라우팅 순서, 제한 정책, 회로·사용량 상태를 바꿉니다. Docker Compose는 gateway, Redis, 서로 다른 모드의 mock 제공자 3개를 실행합니다. 실험 스크립트가 장애 시나리오와 동시 버스트를 실행해 [JSON 결과](results/experiment_results.json)에 기록합니다.

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---|---|
| 장애 전환 시간과 요청 손실 | primary 장애 중 backup 전환 지연·최종 실패 요청 보고 | 최초 failover 80ms; 장애 모드 요청 6/6 성공, 최종 실패 0건 |
| 서킷 브레이커 상태 | 연속 실패 → 차단 → 복구 시도 로그 | 연속 3회 오류에서 OPEN; 2,000ms cooldown 후 HALF_OPEN → CLOSED 로그 확인; 복구 probe까지 2,336ms |
| 즉시 거부 | 동시 20요청 × 3회, 성공 처리량·전체 응답 p95 | 반복별 5/20 성공·15건 429; 중앙값 95.96 성공 응답/초, p95 50.18ms |
| FIFO 제한 시간 대기 | 동시 20요청 × 3회, 성공 처리량·전체 응답 p95 | 반복별 10, 10, 11/20 성공; 중앙값 8.16 성공 응답/초, p95 1,222.28ms |
| 정상 사용량 집계 | gateway와 제공자 token·합성 비용 합계 비교 | 4건, 92 tokens, 568 micro-USD; 양쪽 집계 정확히 일치 |
| timeout 비용 추적 | timeout 후 mock provider 실제 생성분을 포함해 비교 | 실험 증가분 provider 426 micro-USD, gateway 142 micro-USD; 누락 284 micro-USD, 증가분 회계 일치율 33.33% |

**측정 방식**: Spring Boot·Redis와 3개 mock 제공자를 실제 컨테이너로 실행했습니다. 사용량과 단가는 결정적 합성 규칙이며, 제한 정책은 20 동시요청 burst를 세 번 실행해 중앙값을 보고합니다.

즉시 거부는 응답이 빠르고 HTTP thread의 대기가 적었지만 burst당 5건만 수락했습니다. FIFO 대기 정책은 10, 10, 11건을 수락해 처리 건수를 늘렸지만 p95가 대기 한도에 가까워졌습니다. 대기 중에는 HTTP 요청 thread를 점유하므로 별도 worker 기반 비동기 작업 큐와 자원 특성이 다릅니다. 즉시 거부 성공 처리량은 짧은 burst 전체 wall time을 분모로 한 값이라 지속 처리율로 일반화하지 않습니다.

## 시행착오와 의사결정

- timeout이 발생하면 gateway client 예외가 항상 `ResourceAccessException` 형태로 직접 올라올 것이라 예상했습니다. 실제 로그에서는 응답 변환 오류인 `RestClientException` 안에 `SocketTimeoutException`이 들어 있었고 처음엔 요청이 HTTP 500으로 끝났습니다. 이 wrapper 예외를 제공자 실패 경로에서 잡도록 바꾼 뒤 backup의 HTTP 200 응답을 확인했습니다.
- 정상 응답 4건에서는 합성 token/cost 집계가 정확히 일치했습니다. 그러나 slow 제공자에 600ms 지연과 gateway 250ms timeout을 적용하자 두 개의 지연 생성 응답은 client에 도달하지 않았고 backup 응답만 gateway 집계에 반영됐습니다. 제공자 기준 증가분 426 micro-USD 중 gateway는 142만 기록해, 정상 응답의 정확성만으로 timeout 비용까지 추적할 수 없음을 확인했습니다.
- 20 동시요청 실험은 즉시 거부에서 5건, bounded FIFO wait에서 10·10·11건을 수락했습니다. 선택은 처리 수와 응답 지연의 trade-off입니다. 대기 방식은 더 많은 요청을 수락하지만, thread 점유와 p95 지연을 줄이지 못하므로 비동기 worker queue와는 다른 구조입니다.

## 측정 경계 (한계)

이 프로젝트의 토큰과 가격은 고정한 mock 응답 공식이며 공급자 tokenizer·가격표·청구 내역을 검증하지 않습니다. timeout 뒤 제공자 작업이 계속된 상황은 provider-side mock usage로 관측했습니다. Docker gateway는 `127.0.0.1:8080`에만 바인딩되고 운영 제어 API는 포트폴리오 실험용이므로 외부 서비스 공개에 사용하지 않습니다.

**다음 단계**: 비동기 FIFO 작업 큐와 취소·마감시간 정책, 운영 제어 API 인증, 실제 제공자 요청 ID와 사후 청구 내역 대조를 별도 범위로 검증합니다.

## 실행

프로젝트 디렉터리에서:

```bash
docker compose up --build -d
python3 scripts/run_experiments.py
docker compose down
```

gateway 호출은 `POST http://localhost:8080/v1/chat/completions`에 `{"prompt":"hello"}`를 보내면 됩니다. `X-API-Key`별로 속도 제한 bucket을 나누며, 제출값의 SHA-256만 Redis key에 저장합니다. 자세한 변수·계산식·재현 방법은 [실험 프로토콜](docs/experiment_protocol.md)을 참고하세요.

## 개발 방식 (AI 활용 구분)

| 직접 작성한 것 | Codex가 생성한 것 |
|---|---|
| WO-18 범위, Spring 백엔드 경력 연계 요구, 장애·부하·비용 Ship Gate | Spring Boot 게이트웨이, Redis limiter, mock 제공자 구성, 실행 시나리오와 근거 보고서 |

## 용어집

| 용어 | 뜻 |
|---|---|
| 대규모 언어 모델 (Large Language Model, LLM) | 게이트웨이가 중계할 모델 API의 유형입니다. 실험에서는 외부 API 대신 mock provider를 사용합니다. |
| 동시 요청 burst 처리량 (Concurrent Burst Throughput) | 정해진 동시 요청 묶음에서 성공 응답 수를 완료 wall time으로 나눈 값입니다. 짧은 burst 측정이어서 지속 처리율과 다릅니다. |
| 모의 제공자 (Mock Provider) | 정상·실패·지연 응답을 결정적으로 재현하는 서버입니다. 외부 모델 계정 없이 장애 시나리오와 사용량 집계를 검증합니다. |
| 백분위 95 응답 지연 (95th-Percentile Latency, p95) | 응답 지연을 정렬했을 때 95%가 이 값 이내에 끝나는 경계입니다. 비교에는 HTTP 429 응답도 포함합니다. |
| 서버 오류 (HTTP 5xx Server Error) | 제공자 측 서버 실패 응답군이며 서킷 실패와 재시도 판단에 사용합니다. |
| 서킷 브레이커 (Circuit Breaker) | 연속 실패한 제공자 호출을 일정 기간 차단하고 반개방(HALF_OPEN) probe로 복구를 확인합니다. 반복 호출이 장애를 키우지 않도록 필요합니다. |
| 속도 제한 (Rate Limiting) | API key bucket이 허용한 token만 요청을 처리해 과도한 호출을 제한합니다. 이 실험에서는 즉시 HTTP 429와 FIFO 대기를 비교합니다. |
| 응답 시간 초과 (Response Timeout) | gateway가 제공자 응답을 기다리는 상한이며 250ms로 설정했습니다. client 대기가 끝나도 provider server의 처리 작업은 계속될 수 있습니다. |
| 인공지능 게이트웨이 (Artificial Intelligence Gateway) | 여러 LLM 제공자 사이에서 라우팅, 재시도, 속도 제한, 사용량 집계를 맡는 HTTP 진입점입니다. 이 프로젝트의 주요 구현 대상입니다. |
| 입력 token (Prompt Token) | 입력 문자열에서 mock 규칙 `ceil(문자 수 / 4)`로 산출한 입력량입니다. 실제 tokenizer 결과와 구분하기 위해 사용합니다. |
| 자바 백엔드 프레임워크 (Spring Boot Framework) | Java HTTP API와 실행 구성을 만드는 프레임워크입니다. Spring 백엔드 경력과 연결하기 위해 이 프로젝트의 기반으로 선택했습니다. |
| 장애조치 (Failover) | 주 제공자 호출이 실패하면 우선순위가 다음인 제공자로 요청을 넘깁니다. 이 프로젝트는 응답과 최종 실패 수로 전환을 기록합니다. |
| 재시도 (Retry) | 재시도 가능한 서버 오류와 전송 예외에 동일 제공자 호출을 다시 시도합니다. 제공자별 호출 상한은 두 번입니다. |
| 제한 시간 FIFO 대기 정책 (Bounded-Wait First-In, First-Out Queue Policy) | 요청 ticket을 Redis FIFO 목록에 넣고 token이 생길 때까지 HTTP request thread가 한정된 시간 기다립니다. worker 기반 비동기 큐와 자원 특성이 다릅니다. |
| 출력 token (Completion Token) | mock provider가 생성 응답마다 기록하는 출력량이며 16으로 고정했습니다. |
| 합성 비용 (Synthetic Cost) | 입력 token당 2, 출력 token당 8 micro-USD를 적용한 실험용 금액입니다. 상용 API 가격이나 청구액과 구분합니다. |
| Redis (Remote Dictionary Server) | 토큰 bucket 상태와 FIFO 대기열을 공유하는 저장소입니다. gateway는 Lua 원자 연산으로 동시 차감과 대기 순서를 관리합니다. |
| Redis Lua 원자 연산 (Redis Lua Atomic Script) | bucket token 확인·차감과 FIFO head 처리를 Redis에서 원자적으로 실행해 동시 요청 간 상태 경합을 막습니다. |
| SHA-256 해시 (Secure Hash Algorithm 256-bit) | 입력 API key를 고정 길이 식별자로 변환합니다. Redis에는 원래 API key 문자열을 저장하지 않습니다. |

## English Technical Summary

WO-18 implements a Spring Boot gateway in front of three deterministic mock providers, with Redis Lua token-bucket rate limiting, bounded retries, a circuit breaker, provider failover, and usage accounting. In a six-request primary outage scenario, all client requests completed through the backup; the first measured failover took 80 ms and final request loss was zero. Across three bursts of 20 concurrent requests, immediate rejection admitted 5 requests with a median all-response p95 of 50.18 ms, while the bounded FIFO wait admitted a median of 10 with a 1,222.28 ms p95. Normal mock usage matched exactly, but a timeout experiment exposed two provider generations whose responses did not reach the gateway: the incremental cost ledger recorded 142 of 426 micro-USD, or 33.33% accounting accuracy for that scenario. These are synthetic measurements, not commercial provider billing results.
