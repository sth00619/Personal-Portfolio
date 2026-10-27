"""Regression checks for FUNSD link parsing, geometry, and link metrics."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from PIL import Image

from src.dataset import Entity, PairExample, load_split
from src.evaluation import _prf, paired_document_inference
from src.features import layout_vector
from src.model import fit_link_model, predict_links
from src.rules import _best_threshold


def _entity(entity_id: int, text: str, label: str, box: tuple[float, float, float, float]) -> Entity:
    """Create a compact synthetic entity for unit tests."""
    return Entity("doc", entity_id, text, label, box, 1000.0, 1000.0)


def test_funssd_split_parser_preserves_candidate_pairs(tmp_path: Path) -> None:
    """The loader expands all question-answer pairs but labels the linked one."""
    split = tmp_path / "training_data"
    (split / "annotations").mkdir(parents=True)
    (split / "images").mkdir()
    form = [
        {"id": 1, "text": "Name", "label": "question", "box": [10, 10, 50, 30], "linking": [[1, 3]]},
        {"id": 2, "text": "Date", "label": "question", "box": [10, 50, 50, 70], "linking": []},
        {"id": 3, "text": "Ada", "label": "answer", "box": [100, 10, 140, 30], "linking": [[1, 3]]},
    ]
    (split / "annotations" / "sample.json").write_text(json.dumps({"form": form}), encoding="utf-8")
    Image.new("RGB", (200, 100), "white").save(split / "images" / "sample.png")

    rows = load_split(tmp_path, "training_data")

    assert len(rows) == 2
    assert sum(row.linked for row in rows) == 1
    assert next(row for row in rows if row.linked).question.text == "Name"


def test_layout_features_are_normalized_and_directional() -> None:
    """Relative direction and proximity features retain their intended signs."""
    row = PairExample(
        "doc",
        _entity(1, "Name", "question", (100, 100, 200, 140)),
        _entity(2, "Ada", "answer", (250, 100, 350, 140)),
        True,
    )

    features = layout_vector(row)

    assert features.shape == (10,)
    assert 0 < features[0] < 1  # answer is to the right
    assert features[5] == 1.0  # same row
    assert features[7] == 0.0  # answer is level with the question, not below it


def test_pair_link_metrics_and_paired_bootstrap() -> None:
    """Link F1 uses exact relation counts and inference resamples documents."""
    labels = np.asarray([True, False, True, False])
    text_predictions = np.asarray([True, True, False, False])
    layout_predictions = np.asarray([True, False, True, False])
    docs = np.asarray(["a", "a", "b", "b"])

    metrics = _prf(labels, layout_predictions)
    inference = paired_document_inference(labels, text_predictions, layout_predictions, docs)

    assert metrics["f1"] == 1.0
    assert inference["document_count"] == 2
    assert inference["f1_delta_b_minus_a"] > 0.0
    assert len(inference["paired_document_bootstrap_95_ci"]) == 2


def test_model_selects_threshold_from_grouped_train_predictions() -> None:
    """Threshold is learned with held-out document groups, not fixed at 0.5."""
    features = csr_matrix(
        np.asarray(
            [
                [0.0, 1.0], [0.1, 0.9], [1.0, 0.0], [0.9, 0.1],
                [0.05, 0.95], [0.95, 0.05], [0.2, 0.8], [0.8, 0.2],
                [0.15, 0.85], [0.85, 0.15],
            ]
        )
    )
    labels = np.asarray([True, True, False, False, True, False, True, False, True, False])
    groups = np.asarray(["a", "a", "b", "b", "c", "c", "d", "d", "e", "e"])

    model = fit_link_model(features, labels, groups, uses_layout=True)

    assert 0.0 <= model.threshold <= 1.0
    assert 0.0 <= model.cv_f1 <= 1.0
    assert len(predict_links(model, features)) == len(labels)


def test_coordinate_rule_selects_cutoff_with_cumulative_counts() -> None:
    """The distance rule chooses the F1-maximizing cutoff without quadratic scans."""
    distances = np.asarray([0.1, 0.2, 0.3, 0.4])
    labels = np.asarray([True, False, True, False])

    assert _best_threshold(distances, labels) == 0.3
