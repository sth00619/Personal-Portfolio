"""Command-line entry point for the WO-13 fraud experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import ExperimentConfig
from src.pipeline import run_experiment


def parse_args() -> argparse.Namespace:
    """Parse reproducibility overrides for data, results, and model size."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--n-estimators", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    """Build the typed configuration and execute all Ship Gate comparisons."""

    args = parse_args()
    defaults = ExperimentConfig()
    config = ExperimentConfig(
        data_dir=args.data_dir or defaults.data_dir,
        results_dir=args.results_dir or defaults.results_dir,
        n_estimators=args.n_estimators or defaults.n_estimators,
    )
    summary = run_experiment(config)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
