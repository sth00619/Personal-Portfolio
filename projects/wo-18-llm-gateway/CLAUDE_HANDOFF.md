# WO-18 Claude 전달 핸드오프

## 근거 장부

| 주장 후보 | 코드·커밋·로그·측정 근거 | 실제 관측값 | 누가 질문/구현/시험/결정했나 | 상태 |
|---|---|---|---|---|
| Spring Boot 구성이 경력 연계 목표에 맞는다 | `pom.xml`, `src/main/java`, `Dockerfile`, WO-18 시작 지침 | Java 17 source level, Spring Boot 3.5.16; Compose 컨테이너는 Java 21 사용 | 사용자 제공 지침이 기존 Spring 경력 연계를 요구; Codex가 Spring Boot 선택·구현 | 확인됨 |
| primary 장애에서 backup 자동 전환이 수행된다 | `scripts/run_experiments.py`, `results/experiment_results.json`, `/admin/metrics`, gateway transition logs | primary FAIL_ALL, 6개 클라이언트 요청 모두 HTTP 200, backup 6건, 최초 failover 80ms, 최종 유실 0건 | WO가 장애 전환 계측을 요구; Codex가 fault scenario 구현·실행 | 확인됨 |
| circuit breaker가 차단 후 복구한다 | `CircuitBreakerRegistry.java`, experiment JSON, gateway log excerpts | 연속 실패 3건 → OPEN; 2,000ms 설정; 정상 모드 복귀 즉시 backup, cooldown 뒤 2,336ms 측정 구간에서 HALF_OPEN → CLOSED | Codex가 임계값·cooldown을 명시 설정하고 로그로 확인; 사용자 지정 수치는 아님 | 확인됨 |
| 동시 부하에서 거부와 FIFO 대기 정책은 다른 trade-off를 보인다 | `TokenBucketRateLimiter.java`, `scripts/run_experiments.py`, experiment JSON | 정책별 20 concurrent × 3. REJECT 성공 매회 5, p95 중앙값 50.18ms, 성공처리량 중앙값 95.963/s; FIFO QUEUE 성공 10/10/11, p95 1,222.28ms, 성공처리량 8.157/s. 전체 응답 p95에 429 포함 | WO가 비교를 요구; Codex가 5-token/5 refill bucket과 1,200ms 제한을 설정·측정 | 확인됨 |
| 완료 응답의 mock usage 합계는 gateway와 제공자에서 일치한다 | `/admin/usage`, `GatewayMetrics.java`, `MockProviderService.java`, experiment JSON | 정상 응답 4건에서 92 tokens, 568 micro-USD 양쪽 동일 | Codex가 합성 규칙 및 비교 구현·실행 | 확인됨 |
| provider timeout은 gateway ledger가 놓치는 mock 비용을 만들 수 있다 | `ProviderRoutingService.java`, `MockProviderService.java`, `experiment_results.json` | slow 첫 순위, 600ms 생성 지연, 250ms client timeout; backup 성공. 실험 증가분 provider 426 micro-USD, gateway 142, 누락 284, 증가분 회계 정확도 33.333% | Codex가 응답 미도달 시 provider-side 생성 계측을 비교하도록 설정·측정 | 확인됨 |
| 재현 조건과 API key 저장 경계를 확인할 수 있다 | `compose.yaml`, `TokenBucketRateLimiter.java`, `docs/experiment_protocol.md` | Redis 7.4, Java 21 컨테이너; Redis Lua로 토큰 갱신; 원시 API key 대신 SHA-256 bucket ID 저장; HTTP 포트 localhost에만 공개 | Codex 구현·Compose 확인 | 확인됨 |

## 판단 장면

### 1. client timeout 예외를 backup 경로에 연결하기

- 상태: 이번에 새로 검증
- 맥락: slow mock 제공자의 생성 시간은 600ms, gateway의 connect/read timeout은 250ms로 두었다. timeout이 생겨도 같은 제공자 재시도와 backup 전환을 통해 client에 정상 응답을 줄 수 있는지 확인해야 했다.
- 첫 가설: Spring HTTP client의 읽기 timeout은 `ResourceAccessException`으로 나와 같은 실패 분기에서 처리될 것이라고 예상했다. 이는 구현 전 Codex의 라이브러리 동작 가정이다.
- 대안: 연결·응답 예외를 좁게 분류하거나, Spring `RestClientException` 계열을 provider 호출 실패로 포착하고 다음 route로 이동할 수 있었다.
- 판단 기준: 실제 timeout을 500 오류로 노출하지 않고 retry/circuit/failover 경로에 진입하는지, 실패를 숨기지 않고 반환 상태와 provider usage를 관측할 수 있는지.
- 실험: primary/backup/slow route에서 slow를 첫 순위로 설정했다. provider 응답 생성 600ms, gateway read timeout 250ms, 최대 provider 호출 2회, 이후 backup으로 전환했다. 실행 명령은 프로젝트 폴더에서 `python3 scripts/run_experiments.py`다.
- 관측: 첫 실행은 HTTP 500이었고 gateway log root cause는 `SocketTimeoutException`, 상위 예외는 응답 변환 과정의 `RestClientException`이었다. 예외 경로를 넓힌 후 같은 시나리오에서 HTTP 200, backup 응답을 얻었다. provider는 지연 생성 2건도 집계했다.
- 뜻밖의 결과: timeout 원인이 `ResourceAccessException` 타입으로 바로 전달되지 않아 좁은 catch 분기 밖으로 빠졌다. 또한 gateway가 timeout했다고 server-side mock 작업이 취소되지 않았다.
- 결정: RestClient provider 호출의 예외를 한 번 재시도하고, breaker를 기록한 뒤 backup으로 이동하게 했다. 실제 retry 횟수·실패는 결과와 로그에 남긴다. 예외 범위 결정과 수정은 Codex 판단이다.
- 한계: 실제 LLM 공급자 SDK의 오류 종류, remote cancellation, client disconnect semantics를 검증한 것은 아니다.

### 2. 즉시 거부와 제한 시간 대기 중 무엇을 택할 것인가

- 상태: 이번에 새로 검증
- 맥락: 초과 요청을 429로 즉시 거절하거나 refill token을 기다리게 하면 사용자 경험과 server thread 점유가 달라진다.
- 첫 가설: bounded wait가 더 많은 요청을 성공시키고, 제한 시간이 짧으면 응답 지연도 관리 가능할 것이라고 예상했다.
- 대안: 즉시 거부는 응답이 빠르지만 요청 일부를 처리하지 않고, FIFO 대기는 수락 건수를 높이는 대신 기다리는 HTTP 요청 thread를 유지한다. 별도 worker 기반 비동기 queue를 둘 수도 있다.
- 판단 기준: 20개 동시 burst에서 성공 응답 수, 모든 응답을 포함한 p95, 성공 응답/전체 burst wall time을 함께 비교한다. p95 계산에서 429 응답은 제외하지 않는다.
- 실험: initial capacity 5 tokens, refill 5 tokens/second, queue wait limit 1,200ms, 각 정책의 독립 key, 20 concurrent 요청 × 3 반복. `results/experiment_results.json`에 반복별 값을 남겼다.
- 관측: REJECT는 세 반복 각각 5/20 성공·15/20 429, 중앙 p95 50.18ms, 중앙 성공 처리량 95.963/s. QUEUE는 10/20, 10/20, 11/20 성공·나머지 429, 중앙 p95 1,222.28ms, 중앙 성공 처리량 8.157/s.
- 뜻밖의 결과: 대기 정책은 성공 요청 수 중앙값을 두 배로 늘렸지만 p95를 1.2초 이상으로 올렸으며, 실험의 한정 burst 기준 성공 처리량은 더 낮았다. 빠른 429가 일부 요청을 포기하므로 짧은 burst 처리량만 놓고 비교하는 것도 전체 수락률을 숨길 수 있다.
- 결정: 기본 정책은 `REJECT`; `QUEUE`는 제한 시간 대기의 비용을 비교하는 선택 가능한 실험 정책으로 유지한다. 실제 asynchronous FIFO queue가 필요하다면 별도 작업으로 구현·측정한다. 선택은 Codex 판단이며 사용자 지정 선택은 아니다.
- 한계: single host/one gateway replica의 짧은 burst 측정이다. 지속 부하, 여러 gateway 간 fairness, thread pool 포화, 장시간 tail latency를 주장하지 않는다.

### 3. gateway 비용과 provider generation 사용량이 달라진 이유

- 상태: 이번에 새로 검증
- 맥락: 정상 mock 응답에서는 provider response의 usage를 gateway가 기록한다. 그러나 timeout 응답이 원격 provider에서 이미 생성됐다면 gateway는 해당 usage를 받지 못할 수 있다.
- 첫 가설: 완료된 정상 응답에서 두 ledger가 정확히 일치하면 비용 추적 규칙이 검증될 수 있을 것으로 봤다.
- 대안: 성공 응답만 비교하거나, timeout 뒤 provider server-side usage까지 대조해 미도달 응답의 영향을 확인할 수 있었다.
- 판단 기준: 실험 baseline을 먼저 기록하고, 느린 요청 전후의 비용 증가분을 provider-side generated usage와 gateway-received usage로 비교한다.
- 실험: 정상 응답 4건을 baseline으로 계측했다. 입력 token은 `ceil(prompt chars / 4)`(최소 1), 출력은 요청마다 16, synthetic unit cost는 입력 token당 2·출력 token당 8 micro-USD다. 이후 slow route 첫 순위, provider delay 600ms, gateway timeout 250ms로 1개 요청을 보내고 1초 뒤 provider usage를 확인했다.
- 관측: 정상 baseline은 양쪽 92 tokens/568 micro-USD로 일치. timeout 시나리오 증가분은 provider-side 3회 생성 426 micro-USD, gateway는 backup 응답 1회 142 micro-USD였다. 284 micro-USD 누락, 증가분 기준 정확도 `1 - |426-142|/426 = 0.333333`이다.
- 뜻밖의 결과: 사용량 집계가 정상 응답 기준 100% 일치해도, 응답 전송 timeout과 원격 처리 완료 사이의 간극에서 합성 비용의 2/3을 놓쳤다.
- 결정: gateway response usage는 기본 ledger로 유지하지만, timeout 비용 정합성에는 provider request ID와 사후 provider usage/billing reconciliation이 필요하다고 기록한다. 여기서 정한 비용 값은 mock 전용이며 상용 가격이 아니다.
- 한계: 실제 provider의 invoice 단위와 server-side 토큰 발생 타이밍을 검증하지 않았다. timeout이 provider에서 과금됐다는 상용 환경 주장을 하지 않는다.

## 사용자 결정과 Claude 요청

- 사용자가 전달한 범위: WO-18의 LLM gateway, Spring Boot/FastAPI 선택, provider failover·rate policy·circuit log·usage Ship Gate. 시작 지침은 기존 Spring 백엔드 경력과 연결을 강조했다.
- Codex 판단: Spring Boot 선택, Redis Lua limiter, provider timeout 250ms, bucket 5/5, circuit threshold 3/cooldown 2,000ms, queue cap 1,200ms, 20 동시 요청×3회, 합성 token/price formula 및 읽기 timeout 실험.
- 사용자에게 묻지 않은 기술 설정은 Codex가 결정했고, SONG의 사후 선택·승인으로 표현하지 않는다.
- Claude 전달 자료: 프로젝트 README, 이 판단 장면 및 근거 장부, `docs/experiment_protocol.md`, `results/experiment_results.json`.
- README 또는 Notion에서 실측 평균·단일 burst를 지속 처리량으로 일반화하지 않는다. synthetic cost는 실제 provider 청구액과 구분하고 timeout시 gateway ledger 누락을 함께 설명한다.
