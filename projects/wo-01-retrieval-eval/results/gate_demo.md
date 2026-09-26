# Recall regression gate demonstration

Baseline: `hybrid_128`, Recall@10 = `0.8244`. The minimum accepted value is `0.8144` (a one-percentage-point tolerance).

## Passing recomputed candidate

```text
$ python run.py --mode gate
CI candidate recall@10: 0.8244
$ pytest -q tests
.......                                                                  [100%]
7 passed in 2.57s
```

## Deliberately degraded candidate

```text
$ WO01_CANDIDATE=tests/fixtures/bad_candidate.json pytest -q tests/test_regression.py
E   AssertionError: Recall@10 regression: 0.8000 < 0.8144
E   (baseline 0.8244 minus 1.00%)
1 failed in 0.01s
```

The second command is expected to return exit code 1. It exercises the same assertion used by the pull-request workflow.
