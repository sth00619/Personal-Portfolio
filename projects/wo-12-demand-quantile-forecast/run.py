"""Command-line entry point for the WO-12 experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import ExperimentConfig
from src.pipeline import run_experiment


def parse_args() -> argparse.Namespace:
    """Parse reproducibility options exposed by the experiment CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--training-days", type=int, default=None)
    parser.add_argument("--n-estimators", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    """Build configuration overrides and run the measured pipeline."""

    args = parse_args()
    defaults = ExperimentConfig()
    config = ExperimentConfig(
        data_dir=args.data_dir or defaults.data_dir,
        results_dir=args.results_dir or defaults.results_dir,
        training_days=args.training_days or defaults.training_days,
        n_estimators=args.n_estimators or defaults.n_estimators,
    )
    summary = run_experiment(config)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
