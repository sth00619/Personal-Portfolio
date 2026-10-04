"""Ship Gate artifact contract against the measured run."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

from src.report import MODEL_NAMES, validate_result_contract


RESULT_DIR = Path(__file__).resolve().parents[1] / "results"


def test_measured_artifacts_have_matching_metrics() -> None:
    """The committed JSON and CSV must describe one complete test comparison."""
    result = json.loads((RESULT_DIR / "experiment.json").read_text(encoding="utf-8"))
    validate_result_contract(result)
    with (RESULT_DIR / "metrics.csv").open(newline="", encoding="utf-8") as handle:
        csv_rows = {row["model"]: row for row in csv.DictReader(handle)}
    assert set(csv_rows) == set(MODEL_NAMES)
    for name in MODEL_NAMES:
        for metric in ("auc", "log_loss", "ece"):
            assert float(csv_rows[name][metric]) == pytest.approx(result["metrics"][name][metric])
    assert (RESULT_DIR / "calibration_curve.png").stat().st_size > 0


def test_contract_rejects_missing_ece() -> None:
    """Deleting a Ship Gate metric must make regression validation fail."""
    result = json.loads((RESULT_DIR / "experiment.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(result)
    del broken["metrics"]["platt"]["ece"]
    with pytest.raises(ValueError, match="Missing Ship Gate metric"):
        validate_result_contract(broken)
