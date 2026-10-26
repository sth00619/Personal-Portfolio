# ESCI data

Run `python data/download.py` from the project root. The downloader fetches the three official Amazon Science files at a pinned repository revision and verifies the two Git LFS payloads with their published SHA-256 object IDs.

The Task 1 small-version examples and full product table are stored under `data/raw/`. They are excluded from Git. The product table is large; use sufficient free disk space before downloading it.

Source: [Amazon Science ESCI dataset](https://github.com/amazon-science/esci-data). The repository declares Apache-2.0; cite the Shopping Queries Dataset paper when reusing the benchmark. Review the source license and dataset terms before redistribution.
