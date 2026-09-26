"""PR gate: recomputed candidate may lose no more than one recall percentage point."""

import json
import os
from pathlib import Path
import sys
from typing import cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gate import GateResult, assert_recall_within_tolerance

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def _load_result(path: Path) -> GateResult:
    """Load one baseline or candidate result from JSON."""
    return cast(GateResult, json.loads(path.read_text(encoding="utf-8")))


def test_recall_regression_gate() -> None:
    """Fail CI when recomputed Recall@10 drops by more than one percentage point."""
    baseline = _load_result(RESULTS / "baseline.json")
    candidate_path = Path(os.environ.get("WO01_CANDIDATE", RESULTS / "candidate.json"))
    if not candidate_path.exists():
        pytest.skip("Run `python run.py --mode gate` to create results/candidate.json")
    assert_recall_within_tolerance(baseline, _load_result(candidate_path))
