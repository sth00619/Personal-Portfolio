"""PR gate: recomputed candidate may lose no more than one recall percentage point."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def test_recall_regression_gate():
    baseline = json.loads((RESULTS / "baseline.json").read_text(encoding="utf-8"))
    candidate_path = Path(os.environ.get("WO01_CANDIDATE", RESULTS / "candidate.json"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert candidate["config"] == baseline["config"]
    assert candidate["summary"]["all"]["n"] == baseline["summary"]["all"]["n"]
    actual = candidate["summary"]["all"]["recall@10"]
    minimum = baseline["summary"]["all"]["recall@10"] - 0.01
    assert actual >= minimum, f"Recall@10 regression: {actual:.4f} < {minimum:.4f} (baseline minus 1pp)"
