# WO-24 · 한국 주식 백테스트의 생존 편향 점검

> 개인 프로젝트 · 대응 직군: 퀀트 리서치, 금융 데이터 사이언스 · 데이터: KRX 종목 목록·상장폐지 이력, Naver Finance 일별 종가

## 문제 정의

현재 상장된 종목만 과거 구간에 소급해 백테스트하면, 이미 상장폐지된 종목이 과거 유니버스에서 빠지는 생존 편향(survivorship bias)이 생긴다. 이 실험은 같은 모멘텀(momentum) 전략에 현재 상장 표본과 상장폐지 종목을 포함한 표본을 적용해 결과가 얼마나 민감한지 측정한다.

## 가설

상장폐지 이력을 포함하면 현재 생존 종목만 사용한 결과보다 누적 수익률과 샤프 비율(Sharpe ratio)이 낮고 최대 낙폭(maximum drawdown)은 커질 것이다. 거래비용(transaction costs)과 리밸런싱(rebalancing) 주기도 결과를 바꿀 것이다.

## 접근 — 시도 순서

1. **KRX 직접 조회와 pykrx**: 공식 KRX 데이터 마켓플레이스의 상장폐지 목록·시세 화면과 pykrx를 확인했다. 이 실행 환경에서 HTTP 요청은 403을 반환했고, pykrx도 빈 응답을 돌려줬다. 빈 결과를 “상장폐지 종목 0개”로 해석하지 않고 별도 수집 경로를 조사했다.
2. **FinanceDataReader 경로**: `KRX-DELISTING`에서 상장폐지 종목을 읽고 일별 가격을 수집하는 경로가 작동했다. KRX/KOSDAQ 현재 보통주 표본은 시가총액 순으로 정렬해 시장별 균등 간격으로 30개씩 뽑았다. 상장폐지 보통주는 대상 사유에 해당하는 종목 139개를 모두 포함했다. 종목 구성은 `data/universe_manifest.csv`에 고정했다.
3. **거래 시점과 비용 반영**: 매월 말 종가에서 직전 252거래일 수익률을 계산해 상위 10개를 동일 비중(equal weighting)으로 선정하고, 다음 거래일부터 적용했다. 따라서 신호는 리밸런싱 종가 이후 수익률에만 반영된다. 리밸런싱 사이에는 보유 수량을 유지해 종목별 비중이 가격 변동에 따라 움직인다. 거래대금 대비 0·10·25·50bp의 비용 가정을 적용했고, 월별·분기별 리밸런싱을 비교했다.
4. **표본 정제**: 생성된 현재 종목 표본에 우선주가 섞인 것을 발견해 종목명 규칙으로 제거했다. 수정 표본으로 전체 결과를 다시 산출했다. 결과 표와 지표는 고정된 manifest의 현재 실행 결과만 담는다.

## 데이터

- 종목 목록: FinanceDataReader 0.9.202의 `KRX`, `KRX-DELISTING` 데이터 제공자. 원천 안내는 [KRX 상장종목 정보](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp)와 [KRX 상장폐지종목 시세](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp)를 참고했다.
- 가격: FinanceDataReader가 기본 한국 종목 경로에서 읽는 Naver Finance 일별 `Close` 필드.
- 현재 종목 표본: 보통주 60개를 KOSPI와 KOSDAQ에서 각각 시가총액 구간별로 선택했다. 가격 이력은 58개에서 수집됐다.
- 상장폐지 표본: 사유 필터를 통과한 보통주 139개를 모두 포함했고, 가격 이력은 139개에서 수집됐다.
- 모집단 집계: 현재 보통주 후보 2,532개 중 60개를 표본으로 뽑았다. 대상 기간의 상장폐지 보통주 후보 195개 중 합병·완전자회사 편입·상환·만기 사유 56개를 별도 처리 대상에서 제외하고 나머지 139개를 포함했다.
- 원본 가격은 `data/cache/`에 저장하며 Git에 포함하지 않는다. 고정 표본 manifest와 모집단 집계는 분석 경계를 재현할 수 있도록 포함했다.

## 파이프라인

1. FinanceDataReader에서 목록을 가져오거나 고정 manifest를 읽는다.
2. 종목별 일별 종가를 가져와 로컬 무시 대상 캐시에 저장한다.
3. 월말 신호를 계산하고 월간·분기별 포트폴리오 수익률과 거래 비용을 구한다.
4. CSV·JSON 결과를 `results/`에 기록한다.

Python 3.11 환경에서 `make install`로 가상환경을 준비하고 `./data/download.sh`로 데이터를 수집한다. 전체 분석은 `make run`, 회귀 검증은 `make test`로 실행한다. 컨테이너 실행은 `docker compose up --build`를 사용한다.

## 결과 (Ship Gate 표)

| 지표 | 목표 | 실제 |
|---|---:|---:|
| 현재 표본, 월간, 비용 10bp (basis points; 0.1%) 누적 수익률 | 동일 조건으로 비교 | 64.9% |
| 상폐 포함 표본, 월간, 비용 10bp 누적 수익률 | 동일 조건으로 비교 | −8.5% |
| 누적 수익률 차이 (상폐 포함 − 현재 표본) | 편향 민감도 정량화 | −73.4%p |
| 연복리수익률 (Compound Annual Growth Rate, CAGR) 차이 | 편향 민감도 정량화 | −12.6%p (10.8% 대 −1.8%) |
| 샤프 비율 | 같은 기간·전략 비교 | 0.488 대 0.093 |
| 최대 낙폭 (maximum drawdown, MDD) | 같은 기간·전략 비교 | −38.1% 대 −48.8% |
| 가격 이력이 있는 상장폐지 종목 | 필터 후 대상 139개 | 139/139 |
| 상폐 종목의 포트폴리오 편입 | 편입 횟수·종목 수 확인 | 59회 월말 신호 중 38회에 편입, 총 103 종목-월, 서로 다른 종목 24개 |
| 월간 상폐 포함, 거래비용 민감도 | 0·10·25·50bp 비교 | 누적 −5.4% / −8.5% / −13.0% / −20.0% |
| 분기 리밸런싱, 비용 10bp | 월간 리밸런싱과 비교 | 누적 7.8%, CAGR 1.6%, 샤프 0.203, MDD −38.8% |
| Sharpe 3 이상 발생 여부 | 발생 시 원인 분해 | 발생하지 않음. 모든 주요 비교에서 0.004~0.509 범위 |

**측정 방식**: FinanceDataReader 가격 패널에 적용한 단일 팩터 백테스트. 수수료·슬리피지는 실제 체결 비용이 아닌 거래대금 대비 가정값이다. 현재 종목은 균등 표본, 상장폐지 종목은 사유 필터 내 전체 종목이다. CAGR·샤프 비율은 252거래일 기준으로 연환산하며 무위험수익률은 0으로 둔다.

주요 결과 파일은 `results/scenario_summary.csv`, `results/daily_returns.csv`, `results/universe_coverage.csv`, `results/delisted_selection_attribution.json`, `results/run_metadata.json`이다.

## 시행착오와 의사결정

- KRX 직접 조회의 403·빈 응답을 데이터 부재로 간주하지 않고 대체 경로에서 실제 목록과 가격이 반환되는지 확인했다.
- 표본 내 우선주를 발견한 뒤 필터를 보정했다. 현재 목록을 전부 사용하는 대신 시장별 균등 표본을 고정하고, 사유 필터를 통과한 상장폐지 후보는 모두 포함했다.
- 리밸런싱 시점 동률 점수의 종목 순서가 실행마다 달라지는 것을 발견해 종목 코드로 동률을 고정했다. 같은 표본 재실행 결과가 일치하도록 한 뒤 최종 지표를 다시 기록했다.
- 확장 표본의 월간 10bp 결과는 현재 표본보다 누적 수익률이 73.4%p 낮았다. 이는 이 표본과 전략에서 관측한 민감도이며, 전체 시장의 보편적 생존 편향 크기나 인과 효과로 해석하지 않는다.

## 측정 경계 (한계)

- 현재 종목 60개는 현행 목록에서 추출한 표본이라 시점 일치 데이터(point-in-time data) 전체가 아니다. 상장폐지 보통주도 정의한 사유 필터 안에서만 포함된다.
- 합병·완전자회사 편입·상환·만기 56건은 인수 대가, 후계 종목, 상환 현금 흐름을 연결하지 않아 비교에서 제외했다.
- 두 현재 종목은 가격 제공자가 빈 결과를 반환해 현재 표본 60개 중 58개만 분석됐다. 제외 코드와 수집 상태는 `results/universe_coverage.csv`로 확인할 수 있다.
- 마지막 관측 종가를 보유 가치로 유지하는 단순 처리를 사용한다. 거래정지 중 매도 불가, 상장폐지 후 회수금, 합병 대가, 배당, 액면분할·권리변동 조정은 검증하지 않았다.
- 표본 구성, 가격 원천, 단일 모멘텀 팩터, 매월 종가 체결 가정이 결과에 영향을 준다. 누적 수익률 차이 −73.4%p는 본 구성에 한정된 민감도이며 전체 한국 시장의 보편적 생존 편향 크기로 일반화하지 않는다.

**다음 단계**: 시점별 KRX 구성 종목과 상장폐지·합병 대가 연결 자료를 확보하고, 기업행위 조정 및 매도 불가 구간을 반영해 전체 시장 패널로 재검증한다.

## 개발 방식 (AI 활용 구분)

| 직접 작성한 것 | Codex가 생성한 것 |
|---|---|
| 사용자가 WO-24 작업 목표와 저장소 운영 규칙을 제공 | KRX·pykrx 접근 실패 조사, 데이터 경로 비교, 표본·백테스트·비용 계산 코드, 테스트, 결과표와 핸드오프 초안 |

## 용어집

| 용어 | 뜻 |
|---|---|
| 생존 편향 (survivorship bias) | 현재 살아남은 종목만 과거 분석에 넣을 때 실패·상장폐지 종목이 빠지는 선택 편향이다. 이 프로젝트는 그 포함 여부에 따른 결과 민감도를 비교한다. |
| 시점 일치 데이터 (point-in-time data) | 각 과거 시점에 실제로 알 수 있었던 종목 구성과 정보를 보존한 데이터다. 본 프로젝트의 현재 종목 표본은 완전한 시점 일치 패널이 아니다. |
| 모멘텀 (momentum) | 과거 가격 상승률이 높은 자산이 다음 기간에도 강할 수 있다는 신호다. 여기서는 직전 252거래일 수익률로 종목 순위를 정한다. |
| 동일 비중 (equal weighting) | 선택된 종목에 같은 포트폴리오 비중을 주는 방식이다. |
| 리밸런싱 (rebalancing) | 신호에 따라 보유 종목과 비중을 다시 결정하는 과정이다. 월말 신호와 분기 신호를 비교한다. |
| 거래비용 (transaction costs) | 주문 체결에 따르는 수수료·세금·슬리피지 등의 비용이다. 이 실험은 실제 비용표 대신 거래대금 대비 민감도 가정을 쓴다. |
| 룩백 구간 (lookback window) | 신호를 계산하기 위해 과거에서 참조하는 범위다. 본 실험은 252거래일을 사용한다. |
| 연복리수익률 (Compound Annual Growth Rate, CAGR) | 평가 수익을 연 단위 복리 성장률로 환산한 값이다. |
| 베이시스 포인트 (basis point, bp) | 1bp는 1%p의 100분의 1이다. 거래대금 대비 비용 가정을 표기한다. |
| 샤프 비율 (Sharpe ratio) | 변동성 한 단위당 평균 초과수익을 연환산한 지표다. 무위험수익률은 0으로 단순화했다. |
| 최대 낙폭 (maximum drawdown, MDD) | 누적 자산 곡선의 이전 최고점에서 이후 최저점까지의 최대 하락률이다. |
| 회전율 (turnover) | 리밸런싱 때 목표 비중 변화의 절댓값 합이다. 가정 거래비용의 적용 기준이 된다. |
| 미래 정보 누출 (look-ahead bias) | 결정 시점 이후에 공개된 정보를 과거 신호 계산에 쓰는 오류다. 여기서는 월말 종가 신호를 다음 거래일부터 적용한다. |

## English Technical Summary

This experiment measures how a Korean equity momentum backtest changes when 139 eligible delisted stocks are added to a 60-stock sample drawn from current KOSPI and KOSDAQ listings. The strategy ranks securities by trailing 252-session returns, holds the top ten at equal weights, and lets weights drift between monthly or quarterly rebalances. At 10 bps per traded notional, the current-list sample returned 64.9% cumulatively, while the expanded sample returned −8.5%; their Sharpe ratios were 0.488 and 0.093. The comparison is a sensitivity result for a frozen, asymmetric sample, not a point-in-time market estimate. Corporate actions, delisting recovery proceeds, and merger consideration remain outside the model.
