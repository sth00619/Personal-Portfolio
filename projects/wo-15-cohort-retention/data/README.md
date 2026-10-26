# Dataset retrieval

Canonical source: [Olist Brazilian E-Commerce on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The dataset card identifies the license as CC BY-NC-SA; review the current Kaggle terms before reuse. Raw data files are excluded from Git.

Run `python data/download.py` to retrieve the nine CSVs from a revision-pinned public transport mirror. The downloader verifies each file's expected byte size and records its SHA-256 in the console. The Kaggle dataset remains the canonical source; the mirror is a transport path to reproduce analysis without storing credentials.

