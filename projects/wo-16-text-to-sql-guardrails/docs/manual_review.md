# 수동 재검수 기록

가드레일 적용 후 gold가 실행된 오답 후보 25건과 알려진 주석 경계 사례 1건을 분리해 고정했습니다. 판정할 때 질문·증거·스키마·DB 값을 함께 보세요.

| ID | DB | 난이도 | 질문 | 우선 판정 | 근거 메모 |
|---:|---|---|---|---|---|
| 28 | california_schools | challenging | Consider the average difference between K-12 enrollment and 15-17 enrollment of schools that are locally funded, list the names and DOC type of schools which has a difference above this average. | 모델 오류 / gold 의심 | 예측은 없는 schools.name을 참조. 질문의 15–17세와 gold/evidence의 Ages 5–17가 불일치. |
| 62 | california_schools | challenging | What is the total number of non-chartered schools in the county of Los Angeles with a percent (%) of eligible free meals for grades 1 through 12 that is less than 0.18%? | 모델 오류 / gold 의심 | 예측은 없는 frpm.Charter 열을 참조. gold는 질문의 grades 1–12 대신 K-12 비율을 대리 사용. |
| 46 | california_schools | simple | Which state special schools have the highest number of enrollees from grades 1 through 12? | 모델 오류 / gold 의심 | 예측은 State를 반환해 학교명 요청에 실패. gold의 K-12는 grades 1–12와 범위가 다름. |
| 881 | formula_1 | moderate | For the drivers who took part in the race in 1983/7/16, what's their race completion rate? | 모델 오류 / gold 의심 | 예측은 비율 대신 driverid 목록을 반환. gold는 +1/+2/+3 Laps를 time NULL로 계산에서 제외. |
| 1175 | thrombosis_prediction | moderate | How old was the patient who had the highest hemoglobin count at the time of the examination, and what is the doctor's diagnosis? | 모델 오류 / gold 의심 | 예측은 없는 Examination.HGB를 참조. gold의 날짜·진단 원천은 evidence와 불일치하거나 모호. |
| 41 | california_schools | simple | List the names of virtual schools that are among the top 5 in their respective counties based on average reading scores. | 모델 오류 | 없는 satscores.School을 참조하고 county별 상위 5개를 계산하지 못함. |
| 25 | california_schools | moderate | Name schools in Riverside which the average of average math score for SAT is grater than 400, what is the funding type of these schools? | 모델 오류 | 실행 결과가 gold와 다르고 학교별 평균 SAT 수학 점수 조건을 올바르게 계산하지 못함. |
| 83 | california_schools | challenging | Of the schools that offers a magnet program serving a grade span of Kindergarten to 8th grade, how many offers Multiple Provision Types? List the number of cities that offers a Kindergarten to 8th grade span and indicate how many schools are there serving such grade span for each city. | 모델 오류 | 도시별 개수를 요구했으나 (1,1)만 반환해 출력 차원과 의미가 다름. |
| 17 | california_schools | simple | Rank schools by their average score in Writing where the score is greater than 499, showing their charter numbers. | 모델 오류 | charter number 대신 CDS code를 반환함. |
| 36 | california_schools | challenging | Under whose administration is the school with the highest number of students scoring 1500 or more on the SAT? Indicate their full names. | 모델 오류 | 1500점 이상 학생 수의 최대 학교를 찾지 않고 정확히 1500인 행을 사용함. |
| 39 | california_schools | simple | What is the average number of test takers from Fresno schools that opened between 1/1/1980 and 12/31/1980? | 모델 오류 | satscores에 없는 OpenDate 열을 참조함. |
| 47 | california_schools | moderate | What is the monthly average number of schools that opened in Alameda County under the jurisdiction of the Elementary School District in 1980? | 모델 오류 | Alameda County 조건을 누락해 gold와 다른 결과를 반환함. |
| 469 | card_games | moderate | Did the set of cards with "Angel of Mercy" appear on Magic: The Gathering Online? | 모델 오류 | mtgoCode를 cards 테이블에서 조회했으나 해당 열은 sets에 있음. |
| 465 | card_games | moderate | For the set of cards with "Ancestor's Chosen" in it, is there a Korean version of it? | 모델 오류 | set_translations에 없는 uuid로 조인함. |
| 408 | card_games | moderate | How many unknown power cards contain info about the triggered ability | 모델 오류 | OR/AND 괄호가 없어 triggered ability 조건이 power 조건과 다르게 적용됨. |
| 528 | card_games | challenging | List the names of all the cards in the set Hour of Devastation and find the formats in which these cards are legal. | 모델 오류 | 잘못된 set_code 열 및 관계를 사용함. |
| 484 | card_games | moderate | Please list the Italian names of the cards in the set Coldsnap with the highest converted mana cost. | 모델 오류 | set_translations에 없는 uuid로 조인하고 최고 mana cost 결과를 잘못 제한함. |
| 412 | card_games | moderate | What is the foreign name of the card in French of type Creature, normal layout and black border color, by artist Matthew D. Wilson? | 모델 오류 | 요청 조건에 대응하는 필드 이름과 조합이 달라 gold 결과를 반환하지 못함. |
| 487 | card_games | challenging | What is the percentage of incredibly powerful cards in the set Coldsnap? | 모델 오류 | 카드명과 세트명을 혼동해 Coldsnap 세트 비율을 계산하지 못함. |
| 415 | card_games | challenging | What percentage of cards with format commander and legal status do not have a content warning? | 모델 오류 | 대소문자 불일치로 상태 필터 결과가 NULL이 되어 gold와 불일치. |
| 416 | card_games | challenging | What percentage of cards without power are in French? | 모델 오류 | 불어 카드 조건의 조인과 집계가 잘못되어 gold와 불일치. |
| 424 | card_games | simple | What proportion of cards do not have a text box with a normal layout? | 모델 오류 | Textless 열을 사용했으나 실제 스키마의 isTextless를 사용해야 함. |
| 440 | card_games | simple | Which foreign language used by "A Pedra Fellwar"? | 모델 오류 | 외국어 명칭을 foreign_data에서 찾아야 하나 cards의 영어 이름을 조회함. |
| 639 | codebase_community | challenging | Based on posts posted by Community, calculate the percentage of posts that use the R language. | 모델 오류 | codebase_community의 실제 테이블·열과 맞지 않는 참조를 사용함. |
| 587 | codebase_community | moderate | Calculate the average view count of each post tagged as 'humor' and list the title and the comment of each post. | 모델 오류 | tags 조인에 존재하지 않는 PostId 열을 사용함. |

## 실패 후보 상세

### 28 · california_schools / challenging

- 질문: Consider the average difference between K-12 enrollment and 15-17 enrollment of schools that are locally funded, list the names and DOC type of schools which has a difference above this average.
- Evidence: Difference between K-12 enrollment and 15-17 enrollment can be computed by `Enrollment (K-12)` - `Enrollment (Ages 5-17)`
- Gold SQL: `SELECT T2.School, T2.DOC FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.FundingType = 'Locally funded' AND (T1.`Enrollment (K-12)` - T1.`Enrollment (Ages 5-17)`) > (SELECT AVG(T3.`Enrollment (K-12)` - T3.`Enrollment (Ages 5-17)`) FROM frpm AS T3 INNER JOIN schools AS T4 ON T3.CDSCode = T4.CDSCode WHERE T4.FundingType = 'Locally funded')`
- 개선 프롬프트 SQL: `SELECT DISTINCT s.name, s.doctype
FROM schools s
JOIN frpm f ON s.cdscode = f.cdscode
WHERE s.fundingtype = 'Locally Funded'
  AND (s.enrollment12 - s.enrollment517) > (
    SELECT AVG(s1.enrollment12 - s1.enrollment517)
    FROM schools s1
    JOIN frpm f1 ON s1.cdscode = f1.cdscode
    WHERE s1.fundingtype = 'Locally Funded'
  );`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: s.name'}
- 수동 판정: 모델 오류 / gold 의심
- 수동 근거: 예측은 없는 schools.name을 참조. 질문의 15–17세와 gold/evidence의 Ages 5–17가 불일치.

### 62 · california_schools / challenging

- 질문: What is the total number of non-chartered schools in the county of Los Angeles with a percent (%) of eligible free meals for grades 1 through 12 that is less than 0.18%?
- Evidence: non-chartered schools refer to schools whose Charter = 0; K-12 means grades 1 through 12; percent of eligible free rate for K-12 = `Free Meal Count (K-12)` * 100 / `Enrollment (K-12)`
- Gold SQL: `SELECT COUNT(T2.School) FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.County = 'Los Angeles' AND T2.Charter = 0 AND CAST(T1.`Free Meal Count (K-12)` AS REAL) * 100 / T1.`Enrollment (K-12)` < 0.18`
- 개선 프롬프트 SQL: `SELECT COUNT(CDSCode) FROM frpm WHERE Charter = 0 AND `County Name` = 'Los Angeles' AND `Percent (%) Eligible Free (K-12)` < 0.18`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: Charter'}
- 수동 판정: 모델 오류 / gold 의심
- 수동 근거: 예측은 없는 frpm.Charter 열을 참조. gold는 질문의 grades 1–12 대신 K-12 비율을 대리 사용.

### 46 · california_schools / simple

- 질문: Which state special schools have the highest number of enrollees from grades 1 through 12?
- Evidence: State Special Schools refers to DOC = 31; Grades 1 through 12 means K-12
- Gold SQL: `SELECT T2.School FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.DOC = 31 ORDER BY T1.`Enrollment (K-12)` DESC LIMIT 1`
- 개선 프롬프트 SQL: `SELECT DISTINCT T1.State FROM schools AS T1 INNER JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.DOC = 31 AND T2.`Enrollment (K-12)` = (SELECT MAX(`Enrollment (K-12)`) FROM frpm WHERE DOC = 31)`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류 / gold 의심
- 수동 근거: 예측은 State를 반환해 학교명 요청에 실패. gold의 K-12는 grades 1–12와 범위가 다름.

### 881 · formula_1 / moderate

- 질문: For the drivers who took part in the race in 1983/7/16, what's their race completion rate?
- Evidence: DIVIDE(COUNT(driverid when time has value ), (COUNT(driverid )) as percentage; in 1983/7/16 refers to when date = '1983-07-16'
- Gold SQL: `SELECT CAST(COUNT(CASE WHEN T2.time IS NOT NULL THEN T2.driverId END) AS REAL) * 100 / COUNT(T2.driverId) FROM races AS T1 INNER JOIN results AS T2 ON T2.raceId = T1.raceId WHERE T1.date = '1983-07-16'`
- 개선 프롬프트 SQL: `SELECT 
driverid
FROM results
WHERE raceid IN (
    SELECT raceid
    FROM races
    WHERE date = '1983-07-16'
)`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류 / gold 의심
- 수동 근거: 예측은 비율 대신 driverid 목록을 반환. gold는 +1/+2/+3 Laps를 time NULL로 계산에서 제외.

### 1175 · thrombosis_prediction / moderate

- 질문: How old was the patient who had the highest hemoglobin count at the time of the examination, and what is the doctor's diagnosis?
- Evidence: How old the patient refers to SUBTRACT(year(`Examination Date`), year(Birthday)); the highest hemoglobin count refers to MAX(HGB)
- Gold SQL: `SELECT STRFTIME('%Y', T2.Date) - STRFTIME('%Y', T1.Birthday), T1.Diagnosis FROM Patient AS T1 INNER JOIN Laboratory AS T2 ON T1.ID = T2.ID ORDER BY T2.HGB DESC LIMIT 1`
- 개선 프롬프트 SQL: `SELECT T1.ID, T1.`First Date`, T1.Description, T1.Admission, T1.Diagnosis, T2.HGB FROM Patient AS T1 INNER JOIN Examination AS T2 ON T1.ID = T2.ID ORDER BY T2.HGB DESC LIMIT 1`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T2.HGB'}
- 수동 판정: 모델 오류 / gold 의심
- 수동 근거: 예측은 없는 Examination.HGB를 참조. gold의 날짜·진단 원천은 evidence와 불일치하거나 모호.

### 41 · california_schools / simple

- 질문: List the names of virtual schools that are among the top 5 in their respective counties based on average reading scores.
- Evidence: Exclusively virtual refers to Virtual = 'F'; respective counties means PARTITION BY County
- Gold SQL: `SELECT School FROM (SELECT T2.School,T1.AvgScrRead, RANK() OVER (PARTITION BY T2.County ORDER BY T1.AvgScrRead DESC) AS rnk FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.Virtual = 'F' ) ranked_schools WHERE rnk <= 5`
- 개선 프롬프트 SQL: `SELECT DISTINCT T1.School
FROM satscores AS T1
JOIN schools AS T2 ON T1.cds = T2.CDSCode
WHERE T1.rtype = 'F'
GROUP BY T1.cds, T2.County
ORDER BY AVG(T1.AvgScrRead) DESC
LIMIT 5`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T1.School'}
- 수동 판정: 모델 오류
- 수동 근거: 없는 satscores.School을 참조하고 county별 상위 5개를 계산하지 못함.

### 25 · california_schools / moderate

- 질문: Name schools in Riverside which the average of average math score for SAT is grater than 400, what is the funding type of these schools?
- Evidence: Average of average math = sum(average math scores) / count(schools).
- Gold SQL: `SELECT T1.sname, T2.`Charter Funding Type` FROM satscores AS T1 INNER JOIN frpm AS T2 ON T1.cds = T2.CDSCode WHERE T2.`District Name` LIKE 'Riverside%' GROUP BY T1.sname, T2.`Charter Funding Type` HAVING CAST(SUM(T1.AvgScrMath) AS REAL) / COUNT(T1.cds) > 400`
- 개선 프롬프트 SQL: `SELECT DISTINCT T1.FundingType FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T1.County = 'Riverside' GROUP BY T1.FundingType HAVING AVG(T2.AvgScrMath) > 400`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: 실행 결과가 gold와 다르고 학교별 평균 SAT 수학 점수 조건을 올바르게 계산하지 못함.

### 83 · california_schools / challenging

- 질문: Of the schools that offers a magnet program serving a grade span of Kindergarten to 8th grade, how many offers Multiple Provision Types? List the number of cities that offers a Kindergarten to 8th grade span and indicate how many schools are there serving such grade span for each city.
- Evidence: Kindergarten to 8th grade refers to K-8; 'Offers a magnet program' means Magnet = 1; Multiple Provision Types refers to `NSLP Provision Status` = 'Multiple Provision Types'
- Gold SQL: `SELECT T2.City, COUNT(T2.CDSCode) FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T2.Magnet = 1 AND T2.GSoffered = 'K-8' AND T1.`NSLP Provision Status` = 'Multiple Provision Types' GROUP BY T2.City`
- 개선 프롬프트 SQL: `SELECT COUNT(DISTINCT T1.City) AS NumCities, COUNT(T1.CDSCode) AS NumSchools
FROM schools AS T1
JOIN frpm AS T2 ON T1.CDSCode = T2.CDSCode
WHERE T1.GSserved = 'K-8' AND T1.Magnet = 1 AND T2.`NSLP Provision Status` = 'Multiple Provision Types'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: 도시별 개수를 요구했으나 (1,1)만 반환해 출력 차원과 의미가 다름.

### 17 · california_schools / simple

- 질문: Rank schools by their average score in Writing where the score is greater than 499, showing their charter numbers.
- Evidence: Valid charter number means the number is not null
- Gold SQL: `SELECT CharterNum, AvgScrWrite, RANK() OVER (ORDER BY AvgScrWrite DESC) AS WritingScoreRank FROM schools AS T1  INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.AvgScrWrite > 499 AND CharterNum is not null`
- 개선 프롬프트 SQL: `SELECT s.cds, s.cds AS charter_number, AVG(s.AvgScrWrite) AS avg_score
FROM satscores s
WHERE s.AvgScrWrite > 499
GROUP BY s.cds
ORDER BY avg_score DESC`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: charter number 대신 CDS code를 반환함.

### 36 · california_schools / challenging

- 질문: Under whose administration is the school with the highest number of students scoring 1500 or more on the SAT? Indicate their full names.
- Evidence: full name means first name, last name; There are at most 3 administrators for each school; SAT Scores are greater or equal to 1500 refers to NumGE1500
- Gold SQL: `SELECT T2.AdmFName1, T2.AdmLName1, T2.AdmFName2, T2.AdmLName2, T2.AdmFName3, T2.AdmLName3 FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode ORDER BY T1.NumGE1500 DESC LIMIT 1`
- 개선 프롬프트 SQL: `SELECT DISTINCT AdmFName1, AdmLName1 FROM schools AS T1 INNER JOIN satscores AS T2 ON T1.CDSCode = T2.cds WHERE T2.NumGE1500 = 1500 ORDER BY T2.NumGE1500 DESC LIMIT 1`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': ''}
- 수동 판정: 모델 오류
- 수동 근거: 1500점 이상 학생 수의 최대 학교를 찾지 않고 정확히 1500인 행을 사용함.

### 39 · california_schools / simple

- 질문: What is the average number of test takers from Fresno schools that opened between 1/1/1980 and 12/31/1980?
- Evidence: between 1/1/1980 and 12/31/1980 means the year = 1980
- Gold SQL: `SELECT AVG(T1.NumTstTakr) FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE strftime('%Y', T2.OpenDate) = '1980' AND T2.County = 'Fresno'`
- 개선 프롬프트 SQL: `SELECT AVG(NumTstTakr) FROM satscores WHERE rtype = 'FRPM' AND OpenDate BETWEEN '1980-01-01' AND '1980-12-31'`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: OpenDate'}
- 수동 판정: 모델 오류
- 수동 근거: satscores에 없는 OpenDate 열을 참조함.

### 47 · california_schools / moderate

- 질문: What is the monthly average number of schools that opened in Alameda County under the jurisdiction of the Elementary School District in 1980?
- Evidence: Elementary School District refers to DOC = 52; Monthly average number of schools that opened in 1980 = count(schools that opened in 1980) / 12
- Gold SQL: `SELECT CAST(COUNT(School) AS REAL) / 12 FROM schools WHERE DOC = 52 AND County = 'Alameda' AND strftime('%Y', OpenDate) = '1980'`
- 개선 프롬프트 SQL: `SELECT COUNT(CDSCode) /12 FROM schools WHERE DOC = 52 AND OpenDate LIKE '1980%'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: Alameda County 조건을 누락해 gold와 다른 결과를 반환함.

### 469 · card_games / moderate

- 질문: Did the set of cards with "Angel of Mercy" appear on Magic: The Gathering Online?
- Evidence: card set "Angel of Mercy" refers to name = 'Angel of Mercy'; appear on Magic: The Gathering Online refers to mtgoCode is NOT NULL and vice versa
- Gold SQL: `SELECT IIF(T2.mtgoCode IS NOT NULL, 'YES', 'NO') FROM cards AS T1 INNER JOIN sets AS T2 ON T2.code = T1.setCode WHERE T1.name = 'Angel of Mercy'`
- 개선 프롬프트 SQL: `SELECT DISTINCT T1.mtgoCode FROM cards AS T1 INNER JOIN sets AS T2 ON T1.setCode = T2.code WHERE T1.name = 'Angel of Mercy'`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T1.mtgoCode'}
- 수동 판정: 모델 오류
- 수동 근거: mtgoCode를 cards 테이블에서 조회했으나 해당 열은 sets에 있음.

### 465 · card_games / moderate

- 질문: For the set of cards with "Ancestor's Chosen" in it, is there a Korean version of it?
- Evidence: set of cards with "Ancestor''s Chosen" in it refers to name = 'Ancestor''s Chosen'; Korean version refers to language = 'Korean'
- Gold SQL: `SELECT IIF(SUM(CASE WHEN T2.language = 'Korean' AND T2.translation IS NOT NULL THEN 1 ELSE 0 END) > 0, 'YES', 'NO') FROM cards AS T1 INNER JOIN set_translations AS T2 ON T2.setCode = T1.setCode WHERE T1.name = 'Ancestor''s Chosen'`
- 개선 프롬프트 SQL: `SELECT COUNT(T1.uuid) FROM cards AS T1 INNER JOIN set_translations AS T2 ON T1.uuid = T2.uuid WHERE T1.name = 'Ancestor''s Chosen' AND T2.language = 'Korean'`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T2.uuid'}
- 수동 판정: 모델 오류
- 수동 근거: set_translations에 없는 uuid로 조인함.

### 408 · card_games / moderate

- 질문: How many unknown power cards contain info about the triggered ability
- Evidence: unknown power cards refers to power is null or power = '*';contain info about the triggered ability refers to text contains 'triggered ability'
- Gold SQL: `SELECT Count(DISTINCT T1.id) FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE (T1.power IS NULL OR T1.power = '*') AND T2.text LIKE '%triggered ability%'`
- 개선 프롬프트 SQL: `SELECT COUNT(T1.id) FROM cards AS T1 INNER JOIN rulings AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*' AND T2.text LIKE '%triggered ability%'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: OR/AND 괄호가 없어 triggered ability 조건이 power 조건과 다르게 적용됨.

### 528 · card_games / challenging

- 질문: List the names of all the cards in the set Hour of Devastation and find the formats in which these cards are legal.
- Evidence: the set Hour of Devastation refers to set.name = 'Hour of Devastation'; names of all the cards in the set refers to cards.name; legal cards refers to status = 'Legal'; the formats refers to format
- Gold SQL: `SELECT DISTINCT T2.name , CASE WHEN T1.status = 'Legal' THEN T1.format ELSE NULL END FROM legalities AS T1 INNER JOIN cards AS T2 ON T2.uuid = T1.uuid WHERE T2.setCode IN ( SELECT code FROM sets WHERE name = 'Hour of Devastation' )`
- 개선 프롬프트 SQL: `SELECT DISTINCT T1.name, T2.format FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T1.set_code = 'Hour of Devastation' AND T2.status = 'Legal'`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T1.set_code'}
- 수동 판정: 모델 오류
- 수동 근거: 잘못된 set_code 열 및 관계를 사용함.

### 484 · card_games / moderate

- 질문: Please list the Italian names of the cards in the set Coldsnap with the highest converted mana cost.
- Evidence: card set Coldsnap refers to name = 'Coldsnap'; Italian refers to language = 'Italian'; highest converted mana cost refers to MAX(convertedManaCost)
- Gold SQL: `SELECT T2.name FROM foreign_data AS T1 INNER JOIN cards AS T2 ON T2.uuid = T1.uuid INNER JOIN sets AS T3 ON T3.code = T2.setCode WHERE T3.name = 'Coldsnap' AND T1.language = 'Italian' ORDER BY T2.convertedManaCost DESC`
- 개선 프롬프트 SQL: `SELECT DISTINCT T1.name FROM cards AS T1 INNER JOIN set_translations AS T2 ON T1.uuid = T2.uuid WHERE T2.language = 'Italian' AND T1.setCode = 'Coldsnap' GROUP BY T1.name ORDER BY MAX(T1.convertedManaCost) DESC LIMIT 1`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T2.uuid'}
- 수동 판정: 모델 오류
- 수동 근거: set_translations에 없는 uuid로 조인하고 최고 mana cost 결과를 잘못 제한함.

### 412 · card_games / moderate

- 질문: What is the foreign name of the card in French of type Creature, normal layout and black border color, by artist Matthew D. Wilson?
- Evidence: in French refers to language = 'French'; black border color refers to borderColor = 'black'
- Gold SQL: `SELECT name FROM foreign_data WHERE uuid IN ( SELECT uuid FROM cards WHERE types = 'Creature' AND layout = 'normal' AND borderColor = 'black' AND artist = 'Matthew D. Wilson' ) AND language = 'French'`
- 개선 프롬프트 SQL: `SELECT T1.flavorName FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.artist = 'Matthew D. Wilson' AND T1.type = 'Creature' AND T1.layout = 'normal' AND T1.borderColor = 'black' AND T2.language = 'French'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: 요청 조건에 대응하는 필드 이름과 조합이 달라 gold 결과를 반환하지 못함.

### 487 · card_games / challenging

- 질문: What is the percentage of incredibly powerful cards in the set Coldsnap?
- Evidence: card set Coldsnap refers to name = 'Coldsnap'; foil is incredibly powerful refers to cardKingdomFoilId is not null AND cardKingdomId is not null; the percentage of incredibly powerful cards in the set refers to DIVIDE(SUM(incredibly powerful), SUM(name = 'Coldsnap'))*100
- Gold SQL: `SELECT CAST(SUM(CASE WHEN T1.cardKingdomFoilId IS NOT NULL AND T1.cardKingdomId IS NOT NULL THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN sets AS T2 ON T2.code = T1.setCode WHERE T2.name = 'Coldsnap'`
- 개선 프롬프트 SQL: `SELECT CAST(SUM(CASE WHEN cardKingdomFoilId IS NOT NULL AND cardKingdomId IS NOT NULL THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(name) FROM cards WHERE name = 'Coldsnap'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: 카드명과 세트명을 혼동해 Coldsnap 세트 비율을 계산하지 못함.

### 415 · card_games / challenging

- 질문: What percentage of cards with format commander and legal status do not have a content warning?
- Evidence: do not have a content warning refers to hasContentWarning = 0; percentage refers to DIVIDE(COUNT(hasContentWarning = 0),COUNT(ID))*100 where format = 'commander' AND Status = 'legal';
- Gold SQL: `SELECT CAST(SUM(CASE WHEN T1.hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T2.format = 'commander' AND T2.status = 'Legal'`
- 개선 프롬프트 SQL: `SELECT CAST(SUM(CASE WHEN T1.hasContentWarning = 0 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN legalities AS T2 ON T1.uuid = T2.uuid WHERE T2.format = 'commander' AND T2.status = 'legal'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: 대소문자 불일치로 상태 필터 결과가 NULL이 되어 gold와 불일치.

### 416 · card_games / challenging

- 질문: What percentage of cards without power are in French?
- Evidence: in French refers to language = 'French'; cards without power refers to power IS NULL OR power = '*'; percentage = DIVIDE(COUNT(language = 'French' and power is NULL or power = '*'), COUNT( power is NULL or power = '*'))*100
- Gold SQL: `SELECT CAST(SUM(CASE WHEN T2.language = 'French' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.id) FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.power IS NULL OR T1.power = '*'`
- 개선 프롬프트 SQL: `SELECT CAST(SUM(CASE WHEN T1.language = 'French' AND T1.power IS NULL OR T1.power = '*' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(CASE WHEN T1.power IS NULL OR T1.power = '*' THEN 1 ELSE 0 END) FROM foreign_data AS T1 INNER JOIN set_translations AS T2 ON T1.uuid = T2.uuid`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T1.power'}
- 수동 판정: 모델 오류
- 수동 근거: 불어 카드 조건의 조인과 집계가 잘못되어 gold와 불일치.

### 424 · card_games / simple

- 질문: What proportion of cards do not have a text box with a normal layout?
- Evidence: do not have a text box refers to isTextless = 1; proportion refers to DIVIDE(COUNT(Textless = 1 and layout = 'normal'),COUNT(Textless))*100
- Gold SQL: `SELECT CAST(SUM(CASE WHEN isTextless = 1 AND layout = 'normal' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM cards`
- 개선 프롬프트 SQL: `SELECT CAST(SUM(CASE WHEN Textless = 1 AND layout = 'normal' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(Textless) FROM cards`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: Textless'}
- 수동 판정: 모델 오류
- 수동 근거: Textless 열을 사용했으나 실제 스키마의 isTextless를 사용해야 함.

### 440 · card_games / simple

- 질문: Which foreign language used by "A Pedra Fellwar"?
- Evidence: "A Pedra Fellwar" refers to name = 'A Pedra Fellwar'
- Gold SQL: `SELECT DISTINCT language FROM foreign_data WHERE name = 'A Pedra Fellwar'`
- 개선 프롬프트 SQL: `SELECT T2.language FROM cards AS T1 INNER JOIN foreign_data AS T2 ON T1.uuid = T2.uuid WHERE T1.name = 'A Pedra Fellwar'`
- 재채점: {'correct': False, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 수동 판정: 모델 오류
- 수동 근거: 외국어 명칭을 foreign_data에서 찾아야 하나 cards의 영어 이름을 조회함.

### 639 · codebase_community / challenging

- 질문: Based on posts posted by Community, calculate the percentage of posts that use the R language.
- Evidence: DIVIDE(COUNT(PostId WHERE TagName = 'r')), (COUNT(PostId WHERE DisplayName = 'Community')) as percentage; R language refers to tagname = 'r'
- Gold SQL: `SELECT CAST(SUM(IIF(T3.TagName = 'r', 1, 0)) AS REAL) * 100 / COUNT(T1.Id) FROM users AS T1 INNER JOIN postHistory AS T2 ON T1.Id = T2.UserId INNER JOIN tags AS T3 ON T3.ExcerptPostId = T2.PostId WHERE T1.DisplayName = 'Community'`
- 개선 프롬프트 SQL: `SELECT CAST(SUM(CASE WHEN T2.TagName = 'r' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(T1.Id) AS percentage
FROM posts AS T1
JOIN tags AS T2 ON T1.Id = T2.PostId
WHERE T1.OwnerDisplayName = 'Community'`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: T2.PostId'}
- 수동 판정: 모델 오류
- 수동 근거: codebase_community의 실제 테이블·열과 맞지 않는 참조를 사용함.

### 587 · codebase_community / moderate

- 질문: Calculate the average view count of each post tagged as 'humor' and list the title and the comment of each post.
- Evidence: tagged as  'humor' refers to tag = '<humor>'; comment of the post refers to Text; average view count = AVG(ViewCount)
- Gold SQL: `SELECT AVG(T2.ViewCount), T2.Title, T1.Text FROM comments AS T1 INNER JOIN posts AS T2 ON T2.Id = T1.PostId  WHERE T2.Tags = '<humor>' GROUP BY T2.Title, T1.Text `
- 개선 프롬프트 SQL: `SELECT p.Title, c.Text, AVG(p.ViewCount) AS AverageViewCount
FROM posts p
JOIN tags t ON p.Id = t.PostId
JOIN comments c ON p.Id = c.PostId
WHERE t.TagName = '<humor>'
GROUP BY p.Id, p.Title, c.Text`
- 재채점: {'correct': False, 'executed': False, 'blocked': False, 'gold_executable': True, 'reason': 'execution_error: no such column: t.PostId'}
- 수동 판정: 모델 오류
- 수동 근거: tags 조인에 존재하지 않는 PostId 열을 사용함.

## 알려진 주석 경계 사례 (실패 후보와 별도)

### 92 · financial / simple

- 질문: List out the no. of districts that have female average salary is more than 6000 but less than 10000?
- Gold SQL: `SELECT COUNT(DISTINCT T2.district_id)  FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.gender = 'F' AND T2.A11 BETWEEN 6000 AND 10000`
- 개선 프롬프트 SQL: `SELECT COUNT(DISTINCT T1.district_id) FROM client AS T1 INNER JOIN district AS T2 ON T1.district_id = T2.district_id WHERE T1.gender = 'F' AND T2.A11 BETWEEN 6000 AND 10000`
- EX 결과: {'correct': True, 'executed': True, 'blocked': False, 'gold_executable': True, 'reason': 'limit_added:10000'}
- 사람 판정: annotation_audit.md의 스키마·실행 근거를 참조

## 수동 판정 근거

판정 기록은 [manual_review_verdicts.json](manual_review_verdicts.json)에 고정했다. 구체 gold 사례의 스키마·결과 비교는 [annotation_audit.md](annotation_audit.md)에 기록했다.