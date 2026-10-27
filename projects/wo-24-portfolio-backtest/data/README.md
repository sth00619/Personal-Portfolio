# WO-24 data

## Sources

- Listing and delisting metadata: FinanceDataReader's `KRX` and `KRX-DELISTING` listing readers. FinanceDataReader is a community data reader; the underlying exchange reference pages are [KRX listed-stock data](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT238.jsp) and [KRX delisted-stock price history](https://data.krx.co.kr/contents/MDC/STAT/issue/MDCSTAT239.jsp).
- Daily price history: FinanceDataReader's Korean ticker default, which the pinned package routes to Naver Finance's daily chart endpoint. It supplies the `Close` field used here.

## Reproduce or refresh

Run from this project folder:

```bash
./data/download.sh
```

The ticker sample is frozen in `universe_manifest.csv` so reruns use the same symbols. To regenerate the selection from the listing providers, pass `--refresh-universe` to `download.sh`. Price responses are cached under `data/cache/`; the cache and original price files are ignored by Git. The compact ticker manifest and population counts are tracked so the sample can be audited without distributing vendor price files.

## Data handling notes

- The downloaded delisting metadata is filtered to six-digit KOSPI/KOSDAQ share codes in the configured cohort. Preferred shares are excluded. Merger, full-subsidiary, redemption, and maturity reasons are excluded because successor security or redemption value is not modeled.
- The price provider returned histories for every selected delisted security and 58 of 60 current-security sample rows. The two empty current-security responses remain recorded in `results/universe_coverage.csv` and `data/processed/download_failures.csv` (the latter is local and ignored).
- FinanceDataReader returns the source `Close` column. This project does not independently validate split adjustment, dividend reinvestment, rights issues, suspension exits, or post-delisting recovery proceeds.
- Check the providers' current terms before using downloaded data beyond this portfolio analysis.
