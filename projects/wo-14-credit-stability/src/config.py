"""Typed configuration for the WO-14 experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_DIR / "data" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_DIR / "results"


@dataclass(frozen=True)
class ExperimentConfig:
    """Collect reproducible split, stability, and model assumptions."""

    data_dir: Path = DEFAULT_DATA_DIR
    results_dir: Path = DEFAULT_RESULTS_DIR
    id_column: str = "SK_ID_CURR"
    target_column: str = "TARGET"
    train_fraction: float = 0.8
    missing_threshold: float = 0.5
    psi_bins: int = 10
    psi_alert_threshold: float = 0.25
    random_seed: int = 14
    n_estimators: int = 300
    learning_rate: float = 0.04
    num_leaves: int = 31
    min_child_samples: int = 100

