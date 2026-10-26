# Dataset validation ledger

## Source and handling

- Canonical source: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- Reported license: CC BY-NC-SA; reuse must follow the dataset's terms.
- Transport mirror: `bulutttt/olist-raw-data`, pinned to revision `5acf1f37d7197d4979e714721a1ec13a7c3da728`.
- The mirror supplies the original nine CSV filenames. The downloader validates exact byte count and SHA-256 before accepting each file.
- No source CSV or customer-level derived rows are committed. `results/first_order_experience.csv` and `results/survival.csv` contain customer-level records and are excluded from Git.

## File inventory

| Table | Rows | Columns | Bytes | SHA-256 |
|---|---:|---:|---:|---|
| orders | 99,441 | 8 | 17,654,914 | `8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf` |
| customers | 99,441 | 5 | 9,033,957 | `983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2` |
| order_items | 112,650 | 7 | 15,438,671 | `0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279` |
| order_payments | 103,886 | 5 | 5,777,138 | `4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0` |
| order_reviews | 99,224 | 7 | 14,451,670 | `012b61c7593e34f51fa614efdf802b9c7056ce6aae5307ddb93236e7cfc797d7` |
| products | 32,951 | 9 | 2,379,446 | `3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc` |
| sellers | 3,095 | 4 | 174,703 | `1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e` |
| geolocation | 1,000,163 | 5 | 61,273,883 | `b514f6fc991b9566aeba02aa5d67e2c3630f034b60a0e05aa0d082a3b66d88d6` |
| category translation | 71 | 2 | 2,613 | `a81f0d1f27b27e7293f761bc79e3ce8f348ee39c4b3ed3e49bde38f478586278` |

## Analysis population

- All orders: 99,441 order keys, 96,096 `customer_unique_id` values, and 2,997 customers with more than one order (3.1188%). `customer_id` has 99,441 unique values and therefore yields zero repeats by construction.
- Delivered-order population: 96,478 orders, 93,358 unique customers, and 2,801 repeat customers (3.0003%). Cohort, RFM, and survival analyses use delivered orders as confirmed purchases.
- The repeat percentage differs from analyses counting all order statuses because this project excludes canceled, unavailable, and other undelivered statuses from purchase events.
- Monthly records run across 23 purchase-month cohorts. Revenue decomposition excludes the latest observed month, then starts at the first three consecutive months with at least 500 delivered orders each; the 500-order activity rule is fixed in `run.py`.
- Data-integrity checks observed: each CSV loaded into PostgreSQL; order-level joins use `customer_id`; customer purchase aggregation uses `customer_unique_id`; payment rows are pre-aggregated by `order_id` to avoid item-payment fanout.

