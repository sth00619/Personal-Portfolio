# Data acquisition

The canonical source is the
[IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data),
whose files are subject to the Kaggle competition rules. Kaggle requires an
authenticated rules acceptance. `download.py` uses the public
`aliceczr/ieee-fraud-detection` Hugging Face repository as a transport mirror
and validates the original training filenames, byte sizes, and SHA-256 hashes.

```bash
python data/download.py
```

The downloaded transaction and identity files remain in `data/raw/` and are
excluded from Git. The project does not redistribute the competition data.
