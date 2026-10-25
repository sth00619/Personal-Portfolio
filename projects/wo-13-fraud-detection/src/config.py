"""Typed configuration for the WO-13 experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_DIR / "data" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_DIR / "results"


@dataclass(frozen=True)
class ExperimentConfig:
    """Collect reproducible data, model, threshold, and cost assumptions."""

    data_dir: Path = DEFAULT_DATA_DIR
    results_dir: Path = DEFAULT_RESULTS_DIR
    target_column: str = "isFraud"
    id_column: str = "TransactionID"
    time_column: str = "TransactionDT"
    train_fraction: float = 0.8
    inner_train_fraction: float = 0.8
    missing_threshold: float = 0.9
    false_positive_cost: float = 1.0
    false_negative_cost: float = 10.0
    random_seed: int = 13
    n_estimators: int = 260
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_child_samples: int = 80
    latency_samples: int = 500
