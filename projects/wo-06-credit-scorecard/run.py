"""CLI entry point for the WO-06 experiment."""

import os
from pathlib import Path

from src.experiment import END_MONTH, MONTHLY_CAP, START_MONTH, run_experiment

PROJECT_DIR = Path(__file__).resolve().parent


def main() -> None:
    """Run with configurable local data and result directories."""
    data_path = Path(os.getenv("WO06_DATA_PATH", str(PROJECT_DIR / "data" / "LC_loans_granting_model_dataset.csv")))
    results_dir = Path(os.getenv("WO06_RESULTS_DIR", str(PROJECT_DIR / "results")))
    start_month = os.getenv("WO06_START_MONTH", START_MONTH)
    end_month = os.getenv("WO06_END_MONTH", END_MONTH)
    monthly_cap = int(os.getenv("WO06_MONTHLY_CAP", str(MONTHLY_CAP)))
    run_experiment(data_path, results_dir, start_month, end_month, monthly_cap)


if __name__ == "__main__":
    main()
