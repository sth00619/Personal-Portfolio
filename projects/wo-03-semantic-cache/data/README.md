# Data

Run `python data/download.py` to download the `pair-class` split of the Sentence Transformers Quora Duplicate Questions mirror. The downloader pins dataset revision `41f699770310302022a4dd75d4cf903bfef9ea46` and verifies SHA-256 before use.

The file contains the original Quora Question Pairs fields `sentence1`, `sentence2`, and the human duplicate label. The benchmark uses deterministic, non-overlapping rows for threshold tuning and replay. Because the dataset card warns that labels are noisy, a deterministic judge overrides a negative label only when both questions become identical after case, punctuation, and whitespace normalization. The override count is reported in the experiment artifact. The 33 MB parquet file is Git-ignored.

- [Original Kaggle competition](https://www.kaggle.com/c/quora-question-pairs/data) — subject to competition rules
- [Sentence Transformers dataset card](https://huggingface.co/datasets/sentence-transformers/quora-duplicates)
