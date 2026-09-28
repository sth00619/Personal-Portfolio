# WO-03 measured results

## Replay KPIs

| Metric | Result |
|---|---:|
| Queries | 1,000 |
| Response hit rate | 15.90% |
| Cache assist rate | 99.80% |
| Semantic false-hit rate | 0.00% |
| Modeled cost reduction | 67.53% |
| Modeled p50 reduction | 19.75% |
| Modeled p95 reduction | 15.70% |

## Cache tier counts

| Tier | Requests |
|---|---:|
| exact | 150 |
| semantic | 9 |
| prefix | 839 |
| miss | 2 |

## Threshold decision

Selected cosine threshold: **0.993**

Validation precision: 100.00%
Validation recall: 5.18%
Validation false hits: 0

## Prompt-version cache bust

1. First v1 request: `miss`
2. Repeated v1 request: `exact`
3. Same request after switching to v2: `miss`
4. Explicit v1 invalidation removed: `{'redis_entries': 2, 'semantic_entries': 842}`

> Redis and FAISS behavior is executed. Cost and latency values come from the documented deterministic LLM workload model, not a live provider benchmark.
