# WO-11 · GitHub/Notion 전달 메모

## 전달 대상

- 브랜치: `dev/wo-11`
- 프로젝트 README: `projects/wo-11-dispatch-vrptw/README.md`
- 전체 근거: `projects/wo-11-dispatch-vrptw/results/report.json`
- Solomon 표: `results/solomon_benchmark.csv`
- 정책 표: `results/policy_comparison.csv`
- 민감도 표: `results/rider_sensitivity.csv`
- 동적 가격 표: `results/dynamic_price.csv`
- 그래프: `policy_tradeoff.png`, `rider_sensitivity.png`, `dynamic_price.png`

## 공개 문서 핵심 서사

증명하려던 역량은 세 가지다. 첫째, 제약이 있는 차량경로문제를 공식 벤치마크로 검증한다. 둘째, 정적 거리 최적화와 동적 서비스 수준의 차이를 시뮬레이션으로 설명한다. 셋째, 결과가 정책 가정인지 관측 데이터의 인과 효과인지 구분한다.

Solomon 최근접 기준선은 실행 가능하지만 공개 기준보다 4~10대 더 많은 차량을 사용했다. 공개 차량 수를 고정한 OR-Tools 제한시간 탐색의 거리 gap은 C101 0.00%, C104 9.02%, C107 3.06%다. `C103`은 초기 실행 가능해 탐색에 실패해 검증 집합을 바꿨다는 시행착오를 유지한다. OR-Tools 결과를 exact optimum이라고 쓰지 않는다.

TLC 분포 기반 합성 주문을 사용한 SimPy 실험에서 최근접 실시간 정책은 FCFS보다 평균 배달시간과 미배차율을 크게 낮췄다. MIP 배치는 최근접보다 이동거리를 7.92% 줄이고 평균 배달시간은 유사했지만 미배차율은 0.74%p 높았다. 묶음 배치는 미배차율이 가장 낮았지만 평균 배달시간이 길어졌다. 이 결과를 “실시간 vs 배치의 효율·지연 교환관계”로 설명한다.

라이더 10/20/30명에서 MIP 배치의 미배차율은 40.53%/9.35%/0.97%였다. 30명에서는 가동률이 71.66%로 내려가므로 서비스 수준 개선과 유휴 용량 비용을 함께 쓴다.

동적 가격 시나리오는 미배차율을 36.41%에서 13.56%로 낮췄다. 동시에 생성 주문이 200.08건에서 168.50건, 평균 활성 라이더가 10.00명에서 13.87명으로 바뀌었다. 이는 가격의 실제 인과 효과가 아니라 수요·공급 탄력성 가정을 적용한 민감도 결과다.

## Claude에게 요청할 작업

레포 `CLAUDE.md`의 표현 규칙을 적용해 GitHub 루트 README의 WO-11 항목과 Notion Portfolio Hub의 WO-11 케이스를 갱신한다. 문제 정의 → 최근접 기준선 → 계층 목적 수정 → Solomon gap → 동적 정책 확장 → 정책 교환관계 → 수급 민감도 → 다음 검증 순서로 쓴다. 공개 문서에 날짜·프로젝트 소요시간·상대적 시간 표현을 넣지 않는다. 모든 숫자는 프로젝트 README나 결과 파일에서 가져오고, 다음 표현을 지킨다.

- TLC 기록은 배달 로그가 아니라 합성 주문의 시간·OD·운행시간 분포다.
- 거리 단위는 Taxi Zone 대표점 기반 centroid mile이다.
- Solomon VRPTW는 제한시간 메타휴리스틱, 각 배치의 단건 MIP 매칭은 CP-SAT exact다.
- 공개 기준은 SINTEF best-known reference이며 모든 값이 수학적으로 증명된 최적값이라고 확대하지 않는다.
- 동적 가격 결과는 명시적 탄력성 가정의 시나리오다.
