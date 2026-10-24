# Data acquisition

This project uses `calendar.csv` and `sales_train_evaluation.csv` from the M5
Forecasting Accuracy competition. The canonical source is the
[Kaggle competition data page](https://www.kaggle.com/competitions/m5-forecasting-accuracy/data),
whose use is governed by the competition rules. Because Kaggle requires an
authenticated rules acceptance, `download.py` retrieves byte-identical source
files from the public `sktime/tsf-datasets` mirror and verifies their size and
SHA-256 digest.

```bash
python data/download.py
```

Downloaded files and the local manifest stay under `data/raw/` and are excluded
from Git. The experiment loads only the `CA_1` store and `FOODS` category in
chunks; it never melts the complete M5 matrix.

