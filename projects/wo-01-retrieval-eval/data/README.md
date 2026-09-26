# SciFact data

Run `python data/download.py` from the project directory. The script downloads the official BEIR `scifact.zip`, verifies the published MD5 checksum `5f7d1de60b170fc8027bb7898e2efca1`, and extracts it to `data/scifact/`.

Raw data and archives are ignored by Git. If the BEIR host moves, set `BEIR_SCIFACT_URL` to an authorized mirror that serves the identical archive; checksum verification still applies.

Sources and terms:

- [BEIR dataset registry](https://github.com/beir-cellar/beir/wiki/Datasets-available)
- [SciFact license](https://github.com/allenai/scifact/blob/master/LICENSE.md): claims and evidence annotations are CC BY 4.0; corpus abstracts are ODC-By 1.0.
