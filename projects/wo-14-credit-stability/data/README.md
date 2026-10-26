# Raw data contract

The canonical source is the Kaggle [Home Credit Default Risk data page](https://www.kaggle.com/competitions/home-credit-default-risk/data), and use remains subject to the competition rules. Raw files are ignored by Git.

Run `python data/download.py` to retrieve the three required CSV files from a revision-pinned public transport mirror. The downloader rejects files whose byte size or SHA-256 differs from the validated copies. A Kaggle-authenticated download may also be placed in `data/raw/` under the same local filenames.

Required local files:

- `application_train.csv`
- `bureau.csv`
- `previous_application.csv`

`bureau_balance.csv` and the other monthly ledgers are outside this experiment's declared scope. The experiment still performs a true multi-table comparison using two relationship types: credit-bureau histories and previous applications.

