# Dataset validation

## Source and use boundary

- Canonical source: [Home Credit Default Risk — Kaggle data](https://www.kaggle.com/competitions/home-credit-default-risk/data)
- Terms: [Kaggle competition rules](https://www.kaggle.com/competitions/home-credit-default-risk/rules)
- Local retrieval: revision-pinned public transport mirror, validated against this ledger
- Repository policy: raw competition files are excluded from Git

The mirror does not replace Kaggle as the dataset authority. It only makes retrieval possible without storing credentials in the repository. `data/download.py` fixes the mirror revision and rejects any size or SHA-256 mismatch.

## Validated files

| Local file | Rows | Columns | Unique `SK_ID_CURR` | Bytes | SHA-256 |
|---|---:|---:|---:|---:|---|
| `application_train.csv` | 307,511 | 122 | 307,511 | 165,448,797 | `3a230e819e297d7045bbfefdb2d9afa4afef1ab3a8a4bd039c1d3497cb67cb50` |
| `bureau.csv` | 1,716,428 | 17 | 305,811 | 171,733,123 | `75ff59e803bd1c4a02530d13cbf3309107c34ee88cb7d63ec62b2685cac764cb` |
| `previous_application.csv` | 1,670,214 | 37 | 338,857 | 406,367,240 | `53bbcd69f3fe0f43a87b6426f88139346c061955e9c90e29ba6ae2f59637c053` |

`application_train.csv` has 24,825 positive labels, a target rate of 8.0729%. The experiment validates required keys, exact application shape, source row counts, binary labels, unique application IDs, one-row-per-customer aggregates, and row-preserving left joins.

## Scope decision

The analysis uses `bureau.csv` and `previous_application.csv`, producing 112 aggregate features. Monthly tables such as `bureau_balance.csv` are excluded from the declared experiment. This keeps the question focused on whether two distinct relationship histories improve discrimination without hiding the cost of a substantially larger raw-table scope.

