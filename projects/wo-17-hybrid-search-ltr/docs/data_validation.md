# WO-17 data validation record

## Source integrity

The official repository branch was resolved to pinned revision `7916cdf6ab75a462e77f20ab40428a10923998d5`. The downloader fetched both Git LFS payloads and the source CSV. The verified payloads matched their LFS SHA-256 object IDs:

| File | Bytes | SHA-256 |
|---|---:|---|
| `shopping_queries_dataset_examples.parquet` | 51,286,808 | `4a735b693b4a424a6fc67f5be6e4c811495c488bbf66d02a602d308b2744263a` |
| `shopping_queries_dataset_products.parquet` | 1,108,857,465 | `25124442d064d64b26f74082d6fa09438d679efc0c183cf28d19064a2b65a265` |
| `shopping_queries_dataset_sources.csv` | 1,682,802 | `a5fed8ecc016443de40bf3c63098f0e3f23bbe4daa4236f1c38b8c3184778c50` |

## Task 1 subset checks

Filtering the official examples by `small_version=1` and `product_locale=us` produced 601,354 query-product pairs across 29,844 query IDs. The split counts matched the official README: train 20,888 queries/419,653 pairs and test 8,956 queries/181,701 pairs. Each query ID appeared in one split only. The product join used `(product_locale, product_id)`, validated many-to-one cardinality, and produced no missing product titles. No query-product duplicates were observed.

Test candidate depth was 8–95, with mean 20.29, median 16, p90 40, p95 40, and p99 42. Train depth had mean 20.09, median 16, p90 40, p95 40, and p99 43. Products may be shared across query splits as a common catalog; query IDs and their labels remain split-disjoint.

## Candidate-depth discrepancy

The benchmark README describes a list of up to 40 results per query. The verified examples contain larger groups: train query ID `7534`, text `airpods`, has 188 unique product IDs and judgments; the largest test group has 95. No query-product duplicates explain the difference. The implementation retains all judged candidates instead of truncating these groups and reports train/test depths separately. Evaluation remains limited to judged candidates and does not infer labels for the full catalog.
