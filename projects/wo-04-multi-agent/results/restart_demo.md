# WO-04 separate-process restart and approval demonstration

The following commands were run in separate Docker Compose Python containers against one Redis AOF-backed service on 2026-10-04. The `manual` namespace starts with a fresh `C001` synthetic claim. The approver name is a **scripted demo identity**, not a real person's authorization.

```text
$ docker compose run --rm orchestration python manage.py start C001 --events 3
status: RUNNING
next_node: investigator
revision: 3
trace events: 3
payout_count: 0

$ docker compose run --rm orchestration python manage.py resume C001
status: AWAITING_APPROVAL
revision: 11
reviewer_returns: 1
payout_count: 0

$ docker compose run --rm orchestration python manage.py approve C001 --actor synthetic-evaluation-approver
status: PAID
revision: 14
steps: 13
modeled_cost_usd: 0.00381
payout_count: 1
```

The first command stopped after the supervisor checkpointed an `investigator` next-node pointer. A new Python process loaded that snapshot, completed a reviewer return, and stopped before any payout. A third process recorded the explicit demo approval and atomically wrote the synthetic payout plus terminal snapshot. The automated replay also compared this resumed case with an uninterrupted run: terminal state and full node path matched.
