# [WO-04] Claude에게 전달할 실행 결과

## 1. 코드

- 저장소: https://github.com/sth00619/Personal-Portfolio
- 브랜치: `dev/wo-04`
- 경로: `projects/wo-04-multi-agent/`
- 핵심: supervisor 상태 머신, extractor·investigator·reviewer 워커, JSON Schema 핸드오프, Redis 스냅샷, 코드 상한, 승인 게이트, 원자적 합성 지급
- Docker 재현: 프로젝트 폴더에서 `docker compose up --build --abort-on-container-exit --exit-code-from orchestration`

## 2. Ship Gate 결과

| 항목 | 실제 결과 |
|---|---|
| 합성 청구 30건과 경로 트레이스 | 30/30 실행·저장, 정답 종료 상태 30/30 일치 |
| 스냅샷 재개 | 3개 노드 뒤 멈춘 뒤 새 프로세스에서 재개, 중단 없는 실행과 같은 경로·`PAID` |
| reviewer 되돌림 | 5건, 각 1회 재조사 후 종료 |
| 비용 상한 | 건당 모델링 비용 $0.00217~$0.00381, 상한 $0.005; 초과 입력은 코드에서 종료 |
| 사람 승인 | 지급 가능 10건이 먼저 `AWAITING_APPROVAL`에서 중단, 승인 전 지급 기록 0건 |
| 테스트 | 9개 통과; 한도, 승인 거절, 중복 지급, stale snapshot, 계약 위반 포함 |

## 3. 결과물

- `results/experiment.json`: 30건 전체 노드 경로와 노드별 추정 토큰·비용
- `results/report.md`: 사람이 읽는 경로·결과표
- `results/cost_chart.svg` / `.png`: 건당 비용과 상한
- `results/restart_demo.md`: 서로 다른 프로세스에서 재개·승인한 시연 로그
- `README.md`: 구조도, 재현법, 제약과 한계

## 4. 시행착오

- 2,000 추정 토큰 상한은 reviewer 재조사가 있는 정상 사례를 조기 종료했다. 최장 정상 경로 2,025토큰을 확인한 뒤 3,000으로 조정하고 낮은 상한에서 강제 종료되는 테스트를 별도로 남겼다.
- Docker의 `pytest` 실행 파일에서 import 경로가 달라 `python -m pytest`로 통일했다.
- 지급 기록과 최종 상태를 따로 저장하면 중단 시 불일치가 생길 수 있어 Redis Lua에서 한 연산으로 커밋했다.
- reviewer 되돌림은 supervisor에서 1회로 제한하고 별도 전역 스텝 상한을 두었다.

## 5. 인사이트·면접 포인트

- 멀티워커의 가치는 이름이나 페르소나보다 **계약·종료·재개·승인 경계**에서 나왔다. 이 데모는 추출·조사·검토 단계의 입력과 실패 대응이 달라 분리할 이유가 있었지만, 현재 워커가 규칙 기반이므로 단순 단일 함수로도 같은 결론을 낼 수 있다. 실제 LLM 적용 시 단계별 도구·권한·재시도 정책과 트레이스가 더 큰 의미를 갖는다.
- `PAID`가 목표인 케이스도 승인 전 상태는 `AWAITING_APPROVAL`이어야 한다. 자동 재생의 10건 승인은 `synthetic-evaluation-approver` 스크립트로 넣은 시연이며 실제 사람 승인이 아니다.
- 비용 차트는 **실제 API 청구액이 아니다**. 워커는 결정적 규칙이고 각 노드의 토큰·비용은 고정 추정치다. Redis 저장, 재개, 승인·지급 기록은 실제 실행했다.
- 운영 확장 전에 LLM 기반 워커의 실제 토큰 계측, 승인자 인증, 지급 API의 멱등 키, 변조 방지 감사 로그, 장애 복구 실험이 필요하다.

Claude가 README나 Notion에 기록할 때 “자율 LLM 에이전트 30건 처리”, “실제 보험금 지급”, “실제 API 비용 절감”처럼 표현하지 않도록 해 주세요. 이 프로젝트의 입증 범위는 오케스트레이션 제어 흐름입니다.
