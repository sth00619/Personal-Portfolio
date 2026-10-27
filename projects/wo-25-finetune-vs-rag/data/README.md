# Benchmark data

Raw and processed benchmark files are intentionally excluded from Git. From the project directory, run:

```bash
make data
```

The script downloads the pinned official GSM8K train/test parquet files and MMLU test/dev parquet files from Hugging Face. It verifies GSM8K's 7,473/1,319 official row counts, holds 200 GSM8K train rows out for tuning, and samples 10 MMLU test questions from each of 10 fixed subjects. `results/source_manifest.json` records source revisions, licenses, counts, and SHA-256 checksums.

Sources: [GSM8K](https://huggingface.co/datasets/openai/gsm8k) (MIT), [MMLU](https://huggingface.co/datasets/cais/mmlu) (MIT).
