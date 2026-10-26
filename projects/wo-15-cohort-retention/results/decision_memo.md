# WO-15 Decision Memo | Cohort and Retention

## 의사결정 요약

**기존 고객 유지가 성장의 기본 레버라는 가정을 이 데이터만으로 채택하지 않는다.** 완료 주문 기준 고유 고객 재구매율은 3.00%(2,801/93,358)다. RFM 빈도 점수는 대부분의 고객이 1회 구매인 분포를 보존하도록 1회 구매=1, 재구매=5의 두 단계로 구성했다. 반복 구매자를 위한 메시지·혜택 실험은 작고 검증 가능한 후보군에 한정하고, 단골 세그먼트 규모가 충분하다고 가정한 대규모 투자 근거로 사용하지 않는다.

## 근거

- 전체 주문을 `customer_id`로 세면 99,441개 주문 키에서 재구매가 0건이지만, `customer_unique_id`로 묶으면 96,096명 중 2,997명(3.12%)이 반복 주문했다. 주 분석의 완료 주문(배송 완료)은 93,358명 중 2,801명(3.00%)이다.
- 가장 큰 RFM 셀은 `212.0`이며 3,972명, 평균 구매액 70.43이다. 표의 금액 단위는 데이터의 결제 가치 단위를 따른다.
- Kaplan-Meier 추정에서 90일 내 두 번째 완료 주문이 관측되지 않은 생존 확률은 97.87%다. 중도절단 고객은 반복이 없었다고 단정하지 않는다.
- 첫 주문 리뷰 평균은 1회 구매 4.152, 재구매 4.200; Welch t-test p=0.0468 (반복군 n=2,780).
- 첫 주문 배송 지연 비율은 1회 구매 8.19%, 재구매 6.85%; 카이제곱 검정 p=0.0123.
- 첫 구매 상품군 가운데 최소 200명 기준 재구매율이 가장 높은 범주는 `home_appliances`(8.88%, n=676)다. 이는 선택 편향과 다중 비교를 보정하지 않은 관찰값이다.
- 완전한 월만 비교한 매출 최대 하락은 전월 대비 -26.90%. 로그 변화 기여는 고객 수 -0.2761, 고객당 주문 수 -0.0032, 객단가 -0.0341이며 합계가 매출 로그 변화와 일치한다.

## 권고와 경계

다음 투자로는 재구매 가능성이 관측된 고객군의 소규모 유지 실험과 상품 카테고리별 첫 구매 후 재방문 분석을 제안한다. Olist 자료는 마켓플레이스의 관측 주문만 포함하며 비구매 고객, 채널 노출, 고객 유입 비용은 제공하지 않는다. 첫 관측 구매를 실제 최초 구매로 볼 수 없고 자료 종료 시점의 코호트는 추적 기간이 짧다. 리뷰·지연 차이는 상관관계이며 원인 효과가 아니다.

## English summary

The observed delivered-order repeat rate among `customer_unique_id` customers is 3.00%. The order-level `customer_id` would incorrectly imply a zero repeat rate. The cohort, RFM, survival, and first-order experience analyses support a narrowly scoped retention experiment, while the marketplace dataset does not establish causality or represent non-buyers.
