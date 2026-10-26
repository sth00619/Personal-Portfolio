# 알려진 gold 주석 경계 사례

이 파일은 자동 EX 결과와 별개인 수동 gold 검토 기록이다. “의심”은 데이터 주석을 확정적으로 수정했다는 뜻이 아니다. 질문 의도·DB 열 의미·실행 결과가 일치하지 않거나 모호함을 가리키는 근거를 함께 보존한다.

## 사례 28 · California Schools · 15–17과 Ages 5–17

- 질문: locally funded 학교 중 K–12 등록자 수에서 15–17세 등록자 수를 뺀 값이 평균보다 큰 학교를 이름과 DOC 유형으로 묻는다.
- Gold 핵심: `Enrollment (K-12) - Enrollment (Ages 5-17)`을 계산한다.
- 실제 DB 확인: FRPM에는 `Enrollment (Ages 5-17)` 열이 있지만 15–17세 전용 열은 없다. 데이터의 evidence도 “15–17”을 “Ages 5–17”로 바꿔 설명한다.
- 판정: gold 의심. 질문의 연령 범위를 DB 열과 evidence가 서로 다르게 표현한다. 모델은 `schools.name` 등 존재하지 않는 열을 사용해 별도의 스키마 오류를 냈다.

## 사례 46 · California Schools · grades 1–12와 K–12

- 질문: “Which state special schools have the highest number of enrollees from grades 1 through 12?”
- Gold 핵심: `DOC = 31`인 행을 고른 뒤 `Enrollment (K-12)`로 순위를 매긴다.
- 실제 DB 확인: `frpm`에는 `Enrollment (K-12)` 및 `Enrollment (Ages 5-17)`가 있지만 grades 1–12의 독립 집계 열은 없다. Gold 실행 결과는 `California School for the Deaf-Fremont` 한 행이다.
- 판정: gold 의심. K–12에는 kindergarten이 포함되며 질문의 grades 1–12와 동일하지 않다. 다른 열도 학년 범위와 정확히 같다는 자료가 없어 SQL만으로 완전한 대체 답을 정할 수 없다.
- 외부 근거: CIDR 2026 재검토 논문은 이 질문 유형의 예시에서 K–12가 grades 1–12와 같지 않다고 구체적으로 설명한다.

## 사례 62 · California Schools · 자유 급식 비율의 학년 범위

- 질문: 로스앤젤레스 카운티의 비차터 학교에서 grades 1–12 무료 급식 비율이 0.18%보다 낮은 학교 수를 묻는다.
- Gold 핵심: `Free Meal Count (K-12) * 100 / Enrollment (K-12) < 0.18`.
- 실제 DB 확인: 같은 `frpm` 테이블에는 K–12와 Ages 5–17 집계가 있고 grades 1–12만 분리한 값은 없다. Gold SQL은 현재 DB에서 한 학교를 반환한다.
- 판정: gold 의심. 산출식은 K–12의 비율로 질문에서 지정한 학년 범위를 대리한다. 데이터에 해당 범위가 없어 질문의 정확한 의도를 채점할 수 없다.

## 사례 92 · Financial · 엄격한 경계와 BETWEEN

- 질문: 여성 평균 급여가 6,000보다 크고 10,000보다 작은 지역 수를 묻는다.
- Gold 핵심: `A11 BETWEEN 6000 AND 10000`.
- 실제 DB 확인: SQLite `BETWEEN`은 양쪽 끝을 포함한다. Gold 기준 질의와 `A11 > 6000 AND A11 < 10000`으로 바꾼 질의를 각각 실행했을 때 두 결과 모두 69였다.
- 판정: gold 조건식 의심, 이 데이터에서는 반환값 일치. 경계값 행이 없어서 결과 일치(EX)만으로 경계 의미 오류를 발견할 수 없다. 문항 SQL의 의미 검토와 실행 결과 채점을 함께 해야 하는 사례다.

## 사례 881 · Formula 1 · 완주 판정에 사용한 열

- 질문: 1983-07-16 레이스 참가자의 완주율을 묻는다.
- Gold 핵심: `time IS NOT NULL`인 `results` 행을 완주로 세어 전체 참가자 수로 나눈다.
- 실제 DB 확인: 이 레이스는 `raceId = 460`이며 결과 29행 중 `+1 Lap`, `+2 Laps`, `+3 Laps` 상태 12행의 `time`은 NULL이다. Gold 식은 `17.24%`를 반환하지만, `Finished`와 `+n Lap` 상태를 완료로 보면 `17/29 = 58.62%`다.
- 판정: gold 의심. 결과 테이블의 `statusId`와 상태 사전을 사용하면 `+n Lap`도 완주임을 확인할 수 있다. 모델 후보는 드라이버 목록만 반환해 질문의 비율 요청에는 실패했으므로 모델 오류와 gold 의미 오류가 함께 있다.
- 외부 근거: CIDR 재검토 논문은 Formula 1의 ID 881 사례에서 `+n Lap` 상태의 드라이버도 완주했다고 지적한다.

## 사례 1175 · Thrombosis Prediction · diagnosis 참조 모호성

- 질문: 최고 hemoglobin 검사 시 환자 나이와 의사의 진단을 묻는다.
- Gold 핵심: HGB가 가장 높은 `Laboratory` 행을 기준으로 `Patient.Diagnosis`를 반환한다.
- 실제 DB 확인: `Patient`와 `Examination` 양쪽에 `Diagnosis` 열이 존재한다. Gold는 HGB가 최대인 Laboratory 행의 `Date`로 나이를 계산하지만 evidence는 `Examination Date`를 지목한다. 그 환자는 `Patient.Diagnosis = SLE`이고 연결된 Examination 행은 없어 어떤 diagnosis가 의도인지 확인할 수 없다.
- 판정: 모호성 의심. CIDR 분석은 이 ID에서 `Patient.Diagnosis`와 `Examination.Diagnosis` 중 의도된 항목을 질문이 분명히 정하지 않는다고 기록한다. 날짜 원천도 evidence와 gold가 다르다. 모델은 `Examination.HGB`를 참조해 없는 열 오류를 냈다.

## 근거 출처

- Jin et al., “Text-to-SQL Benchmarks are Broken: An In-Depth Analysis of Annotation Errors,” CIDR 2026. 논문은 검토한 BIRD Mini-Dev 498문항 중 52.8%에서 하나 이상의 주석 오류를 확인했고, BIRD Dev 100개 표본 재채점에서 모델별 성능 변화가 나타났다고 보고한다. 본 프로젝트의 표본 오류율로 전용하지 않는다.
- 논문 원문: https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf
- Mini-Dev 데이터 및 평가 안내: https://github.com/bird-bench/mini_dev
