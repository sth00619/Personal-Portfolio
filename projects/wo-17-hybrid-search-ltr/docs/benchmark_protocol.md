# WO-17 benchmark protocol

## Data scope

- Dataset: Amazon Science Shopping Queries Dataset, Task 1 `small_version=1`.
- Locale: `us`, filtering `product_locale` in both examples and products.
- Split: official query-level `train` and `test`; no query is allowed in both.
- Product records can appear as candidates in both query splits, representing a shared catalog. No test query labels enter training.
- Candidate scope: only product IDs with official ESCI judgements for that query. Candidate recall over the full product catalog is not measured.
- Join: `(product_locale, product_id)`, with a many-to-one product join and no missing product title allowed.
- Data revision and expected payload integrity: `source_manifest.json` and `data/download.py`.

## Relevance definitions

- Binary: `E=1`; `S=C=I=0`.
- Graded: `E=3, S=2, C=1, I=0`, used both for LambdaMART training and graded reporting.
- NDCG@10: gain `2^relevance - 1`, discount `log2(rank + 1)`, averaged over all test queries. Queries without an Exact label receive binary NDCG zero; for graded NDCG all-irrelevant lists have zero ideal gain and score zero.
- Binary MRR@10: reciprocal rank of the first Exact result.
- Graded MRR@10: reciprocal rank of the first non-Irrelevant result. This operational definition treats S and C as relevant for MRR, while NDCG retains their graded distinction.

## Methods

1. BM25 Okapi and normalized `all-MiniLM-L6-v2` cosine similarity independently rank each query's judged candidates.
2. Reciprocal Rank Fusion uses `k=60` and sums `1/(k+rank)` from both rankings.
3. LTR features include raw BM25 and cosine scores, both ranks, RRF score, brand match, query/title token overlap, and text lengths.
4. LightGBM `LGBMRanker(objective="lambdarank")` trains on graded relevance using training queries only. Its random seed is fixed; model parameters are recorded in source.
5. Compare RRF with RRF+LTR on the same held-out query candidates using binary and graded NDCG@10/MRR@10.
6. Report split sizes, candidate depth, relevance counts, and gain-based feature importance.

This protocol evaluates candidate reranking on judged examples. Results must not be presented as full-catalog search recall or as directly comparable to Amazon's submitted leaderboard score.
