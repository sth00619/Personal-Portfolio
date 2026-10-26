"""Command-line entry point for WO-14."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import DEFAULT_DATA_DIR, DEFAULT_RESULTS_DIR, ExperimentConfig
from src.pipeline import run_experiment


def parse_args() -> argparse.Namespace:
    """Parse optional local data and result directories."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> None:
    """Run the reproducible experiment and print its compact evidence summary."""

    args = parse_args()
    summary = run_experiment(
        ExperimentConfig(data_dir=args.data_dir, results_dir=args.results_dir)
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

