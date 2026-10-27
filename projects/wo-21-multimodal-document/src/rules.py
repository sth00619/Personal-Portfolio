"""A coordinate-only nearest-distance threshold baseline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import GroupKFold

from src.dataset import PairExample
from src.features import layout_vector

RULE_CV_FOLDS = 5


@dataclass(frozen=True)
class ProximityRule:
    """Distance threshold selected with the training links only."""

    max_normalized_distance: float
    cv_precision: float
    cv_recall: float
    cv_f1: float


def _best_threshold(distances: np.ndarray, labels: np.ndarray) -> float:
    """Choose the closest-distance cutoff maximizing micro F1 on given data."""
    candidates, inverse = np.unique(distances, return_inverse=True)
    candidate_counts = np.bincount(inverse)
    positive_counts = np.bincount(inverse, weights=labels.astype(np.int64))
    predicted_count = np.cumsum(candidate_counts)
    true_positive = np.cumsum(positive_counts)
    false_positive = predicted_count - true_positive
    false_negative = int(np.sum(labels)) - true_positive
    denominator = 2 * true_positive + false_positive + false_negative
    f1_scores = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive, dtype=float),
        where=denominator > 0,
    )
    best_score = float(np.max(f1_scores))
    best_index = int(np.flatnonzero(np.isclose(f1_scores, best_score))[0])
    return float(candidates[best_index])


def fit_proximity_rule(examples: list[PairExample]) -> ProximityRule:
    """Group-cross-validate a distance-only rule and fit its cutoff on train data."""
    labels = np.asarray([row.linked for row in examples], dtype=bool)
    groups = np.asarray([row.document_id for row in examples], dtype=str)
    distances = np.asarray([layout_vector(row)[4] for row in examples], dtype=float)
    if len(np.unique(groups)) < RULE_CV_FOLDS:
        raise ValueError(f"At least {RULE_CV_FOLDS} training documents are needed for the rule baseline")
    out_of_fold = np.zeros(len(labels), dtype=bool)
    splitter = GroupKFold(n_splits=RULE_CV_FOLDS)
    for train_indices, validation_indices in splitter.split(np.arange(len(labels)), labels, groups):
        cutoff = _best_threshold(distances[train_indices], labels[train_indices])
        out_of_fold[validation_indices] = distances[validation_indices] <= cutoff
    tp = int(np.sum(labels & out_of_fold))
    fp = int(np.sum(~labels & out_of_fold))
    fn = int(np.sum(labels & ~out_of_fold))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    cv_f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return ProximityRule(_best_threshold(distances, labels), precision, recall, cv_f1)


def predict_proximity_rule(examples: list[PairExample], rule: ProximityRule) -> np.ndarray:
    """Predict candidate links whose normalized center distance is within cutoff."""
    distances = np.asarray([layout_vector(row)[4] for row in examples], dtype=float)
    return distances <= rule.max_normalized_distance
