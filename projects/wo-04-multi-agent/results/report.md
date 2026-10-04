# WO-04 measured deterministic replay

- Cases: **30**; correct terminal labels: **30/30**
- Reviewer returns: **5**
- Scripted human approvals: **10**; payouts: **10**
- Maximum modeled cost: **$0.003810**; cap: **$0.005000**
- Resume demo: **True** with same terminal `PAID`

Cost and token usage are deterministic estimates for simulated workers; no LLM API was called. Redis snapshots, approval gate, and payout record are executed for real.

| Case | Gold | Terminal | Steps | Returns | Modeled cost (USD) | Path |
|---|---|---|---:|---:|---:|---|
| C001 | PAID | PAID | 13 | 1 | $0.003810 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C002 | PAID | PAID | 13 | 1 | $0.003810 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C003 | PAID | PAID | 13 | 1 | $0.003810 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C004 | PAID | PAID | 13 | 1 | $0.003810 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C005 | PAID | PAID | 13 | 1 | $0.003810 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C006 | PAID | PAID | 9 | 0 | $0.002470 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C007 | PAID | PAID | 9 | 0 | $0.002470 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C008 | PAID | PAID | 9 | 0 | $0.002470 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C009 | PAID | PAID | 9 | 0 | $0.002470 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C010 | PAID | PAID | 9 | 0 | $0.002470 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor → human_approval → supervisor → payout |
| C011 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C012 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C013 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C014 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C015 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C016 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C017 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C018 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C019 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C020 | DENIED | DENIED | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C021 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C022 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C023 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C024 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C025 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C026 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C027 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C028 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C029 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
| C030 | NEEDS_INFO | NEEDS_INFO | 7 | 0 | $0.002170 | supervisor → extractor → supervisor → investigator → supervisor → reviewer → supervisor |
