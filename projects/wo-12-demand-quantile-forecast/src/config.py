"""Experiment configuration for the WO-12 forecasting pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_DIR / "data" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_DIR / "results"


@dataclass(frozen=True)
class ExperimentConfig:
    """Hold all reproducible experiment choices in one typed object."""

    data_dir: Path = DEFAULT_DATA_DIR
    results_dir: Path = DEFAULT_RESULTS_DIR
    store_id: str = "CA_1"
    category_id: str = "FOODS"
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    horizon: int = 28
    fold_count: int = 3
    training_days: int = 420
    intermittent_zero_threshold: float = 0.5
    random_seed: int = 12
    n_estimators: int = 220
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_child_samples: int = 40
    chunk_rows: int = 2_000

