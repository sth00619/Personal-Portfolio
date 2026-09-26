# Measured SciFact test results

Documents: 5183 · judged queries: 300 · relevant pairs: 339

| Configuration | Category | n | Recall@10 | MRR | nDCG@10 |
|---|---|---:|---:|---:|---:|
| bm25_128 | all | 300 | 0.7575 | 0.5942 | 0.6261 |
| bm25_128 | negation | 30 | 0.7167 | 0.6065 | 0.6258 |
| bm25_128 | numeric_or_comparative | 78 | 0.7660 | 0.6123 | 0.6379 |
| bm25_128 | other | 192 | 0.7604 | 0.5849 | 0.6213 |
| dense_128 | all | 300 | 0.8082 | 0.6448 | 0.6767 |
| dense_128 | negation | 30 | 0.8667 | 0.6768 | 0.7215 |
| dense_128 | numeric_or_comparative | 78 | 0.7481 | 0.6557 | 0.6598 |
| dense_128 | other | 192 | 0.8234 | 0.6354 | 0.6765 |
| hybrid_128 | all | 300 | 0.8244 | 0.6647 | 0.6942 |
| hybrid_128 | negation | 30 | 0.8500 | 0.6797 | 0.7153 |
| hybrid_128 | numeric_or_comparative | 78 | 0.8165 | 0.6979 | 0.7092 |
| hybrid_128 | other | 192 | 0.8237 | 0.6488 | 0.6849 |
| bm25_240 | all | 300 | 0.7590 | 0.6171 | 0.6428 |
| bm25_240 | negation | 30 | 0.7667 | 0.6392 | 0.6667 |
| bm25_240 | numeric_or_comparative | 78 | 0.7718 | 0.6290 | 0.6479 |
| bm25_240 | other | 192 | 0.7526 | 0.6088 | 0.6369 |
| dense_240 | all | 300 | 0.8174 | 0.6108 | 0.6558 |
| dense_240 | negation | 30 | 0.8667 | 0.6421 | 0.6949 |
| dense_240 | numeric_or_comparative | 78 | 0.8179 | 0.6337 | 0.6762 |
| dense_240 | other | 192 | 0.8095 | 0.5966 | 0.6414 |
| hybrid_240 | all | 300 | 0.8138 | 0.6567 | 0.6849 |
| hybrid_240 | negation | 30 | 0.8500 | 0.6950 | 0.7263 |
| hybrid_240 | numeric_or_comparative | 78 | 0.8004 | 0.6762 | 0.6922 |
| hybrid_240 | other | 192 | 0.8135 | 0.6428 | 0.6755 |
| hybrid_128_rerank | all | 300 | 0.8323 | 0.6635 | 0.6946 |
| hybrid_128_rerank | negation | 30 | 0.8833 | 0.6361 | 0.6882 |
| hybrid_128_rerank | numeric_or_comparative | 78 | 0.8244 | 0.6709 | 0.6947 |
| hybrid_128_rerank | other | 192 | 0.8276 | 0.6647 | 0.6955 |
