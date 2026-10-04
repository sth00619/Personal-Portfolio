# Data

Download the 167.5 MB [Lending Club loan dataset for granting models](https://zenodo.org/records/11295916) (DOI: 10.5281/zenodo.11295916, CC BY 4.0) with `bash data/download.sh`. The script verifies the Zenodo MD5. Raw CSV is ignored by Git.

The work order recommends Kaggle Home Credit Credit Risk Model Stability. Its competition data requires Kaggle account/rules acceptance in this environment. This project uses the dated, publicly downloadable Lending Club alternative so that measured results can be reproduced without distributing Kaggle data.

The dataset curators retained only final-status loans and application-time variables. `Default=1` means charged off/default; `Default=0` means fully paid. `issue_d` is the origination month, not outcome-observation date. This distinction limits claims about deployment-time label availability.
