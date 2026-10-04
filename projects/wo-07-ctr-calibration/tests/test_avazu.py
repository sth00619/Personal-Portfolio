"""Checks for Avazu source sampling and chronological feature isolation."""

from __future__ import annotations

import gzip
import json
import zlib
from pathlib import Path

import pandas as pd
import pytest
import numpy as np

from data.prepare_avazu import EXPECTED_COLUMNS, EXPECTED_ROWS, EXPECTED_SHA256, sample_stream
from src.avazu import (
    OTHER_TOKEN, RAW_CATEGORIES, AvazuFeatures, chronological_split,
    paired_bootstrap,
)


def avazu_line(identifier: int, click: int, hour: str) -> str:
    """Create one complete synthetic competition record."""
    fields = [str(identifier), str(click), hour, *(["a"] * len(RAW_CATEGORIES))]
    return ",".join(fields) + "\n"


def test_id_hash_sample_audits_all_rows(tmp_path: Path) -> None:
    """Sampling depends on ID alone while full-day counts retain all rows."""
    source = tmp_path / "train.gz"
    destination = tmp_path / "sample.gz"
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write(",".join(EXPECTED_COLUMNS) + "\n")
        for identifier in range(100):
            day = "141021" if identifier < 50 else "141022"
            handle.write(avazu_line(identifier, identifier % 2, day + "00"))
    audit = sample_stream(source, destination, modulus=4, offset=1)
    expected = [
        identifier for identifier in range(100)
        if zlib.crc32(str(identifier).encode("ascii")) % 4 == 1
    ]
    with gzip.open(destination, "rt", encoding="utf-8") as handle:
        selected = [int(line.split(",", 1)[0]) for line in list(handle)[1:]]
    assert selected == expected
    assert audit["source_rows"] == 100
    assert audit["source_day_rows"] == {"141021": 50, "141022": 50}
    assert audit["source_day_clicks"] == {"141021": 25, "141022": 25}
    assert audit["sample_rows"] == len(expected)


def test_avazu_rejects_reverse_time_order(tmp_path: Path) -> None:
    """A later record with an earlier hour invalidates the sample."""
    source = tmp_path / "bad.gz"
    destination = tmp_path / "sample.gz"
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write(",".join(EXPECTED_COLUMNS) + "\n")
        handle.write(avazu_line(1, 0, "14102200"))
        handle.write(avazu_line(2, 1, "14102100"))
    with pytest.raises(ValueError, match="unsorted hour"):
        sample_stream(source, destination, modulus=4, offset=1)
    assert not destination.exists()


def test_avazu_features_fit_only_earlier_days() -> None:
    """Future-only categories become fallback values after train fitting."""
    days = [f"1410{day:02d}" for day in range(21, 31)]
    rows = []
    for day in days:
        for _ in range(4):
            record = {column: "a" if day < "141029" else "future" for column in RAW_CATEGORIES}
            record.update({"day": day, "hour": day + "06", "click": 0})
            rows.append(record)
    split = chronological_split(pd.DataFrame(rows))
    assert (len(split.train), len(split.calibration), len(split.test)) == (24, 8, 8)
    features = AvazuFeatures().fit(split.train)
    transformed = features.transform(split.test)
    assert set(transformed[RAW_CATEGORIES[0]].astype(str)) == {OTHER_TOKEN}
    assert set(transformed["hour_of_day"].astype(str)) == {"06"}
    assert "future" not in features.vocabularies[RAW_CATEGORIES[0]]


def test_paired_bootstrap_zero_for_identical_predictions() -> None:
    """Paired comparisons have zero improvement for identical models."""
    labels = np.array([0, 1, 0, 1] * 20)
    scores = np.linspace(0.1, 0.8, len(labels))
    days = np.array(["day1"] * 40 + ["day2"] * 40)
    result = paired_bootstrap(
        labels, {name: scores.copy() for name in ("baseline", "platt", "isotonic")},
        days, bins=10, repeats=20,
    )
    for improvement in result.values():
        assert improvement["ece_reduction"] == pytest.approx(0)
        assert improvement["log_loss_reduction"] == pytest.approx(0)
        assert improvement["ece_reduction_95_ci"] == pytest.approx([0, 0])


def test_saved_avazu_artifacts_match_source_audit() -> None:
    """Published aggregates retain source provenance and aligned test metrics."""
    output = Path(__file__).resolve().parents[1] / "results" / "avazu"
    if not (output / "report.json").is_file():
        pytest.skip("Run the Avazu experiment to create measured outputs")
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(output / "metrics.csv")
    audit = report["source_audit"]
    assert audit["source_sha256"] == EXPECTED_SHA256
    assert audit["source_rows"] == EXPECTED_ROWS
    assert sum(item["rows"] for item in report["split"].values()) == audit["sample_rows"]
    assert set(metrics.model) == {"baseline", "platt", "isotonic"}
    assert metrics.sample_count.eq(report["split"]["test"]["rows"]).all()
    for row in metrics.itertuples():
        assert row.ece == pytest.approx(report["metrics"][row.model]["ece"])
    assert (output / "calibration_curve.png").is_file()
