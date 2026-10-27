"""Train the fixed text-only and text-plus-layout link classifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import GroupKFold

CLASSIFIER_C = 1.0
MAX_ITER = 1000
CV_FOLDS = 5


@dataclass
class LinkModel:
    """A feature matrix specification paired with a fitted classifier."""

    classifier: LogisticRegression
    uses_layout: bool
    threshold: float
    cv_precision: float
    cv_recall: float
    cv_f1: float


def _new_classifier() -> LogisticRegression:
    """Create the common class-balanced logistic classifier."""
    classifier = LogisticRegression(
        C=CLASSIFIER_C,
        class_weight="balanced",
        max_iter=MAX_ITER,
        solver="liblinear",
        random_state=0,
    )
    return classifier


def fit_link_model(
    features: csr_matrix,
    labels: np.ndarray,
    groups: np.ndarray,
    uses_layout: bool,
    fold_feature_builder: Callable[[np.ndarray, np.ndarray], tuple[csr_matrix, csr_matrix]] | None = None,
) -> LinkModel:
    """Select a threshold with grouped out-of-fold scores, then fit on all train candidates."""
    if len(np.unique(groups)) < CV_FOLDS:
        raise ValueError(f"At least {CV_FOLDS} training documents are needed for threshold selection")
    out_of_fold = np.zeros(len(labels), dtype=float)
    splitter = GroupKFold(n_splits=CV_FOLDS)
    for train_indices, validation_indices in splitter.split(np.arange(len(labels)), labels, groups):
        if fold_feature_builder is None:
            fold_train_features = features[train_indices]
            fold_validation_features = features[validation_indices]
        else:
            fold_train_features, fold_validation_features = fold_feature_builder(
                train_indices, validation_indices
            )
        fold_classifier = _new_classifier()
        fold_classifier.fit(fold_train_features, labels[train_indices])
        out_of_fold[validation_indices] = fold_classifier.predict_proba(fold_validation_features)[:, 1]

    precision, recall, thresholds = precision_recall_curve(labels, out_of_fold)
    f1_scores = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    best_score = float(np.max(f1_scores))
    best_indices = np.flatnonzero(np.isclose(f1_scores, best_score))
    threshold = float(thresholds[best_indices[-1]])
    cv_predictions = out_of_fold >= threshold
    true_positive = int(np.sum(labels & cv_predictions))
    false_positive = int(np.sum(~labels & cv_predictions))
    false_negative = int(np.sum(labels & ~cv_predictions))
    cv_precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    cv_recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    cv_f1 = (
        2 * cv_precision * cv_recall / (cv_precision + cv_recall)
        if cv_precision + cv_recall
        else 0.0
    )
    classifier = _new_classifier()
    classifier.fit(features, labels)
    return LinkModel(
        classifier=classifier,
        uses_layout=uses_layout,
        threshold=threshold,
        cv_precision=cv_precision,
        cv_recall=cv_recall,
        cv_f1=cv_f1,
    )


def predict_links(model: LinkModel, features: csr_matrix) -> np.ndarray:
    """Predict links with a threshold selected only on train-fold predictions."""
    return model.classifier.predict_proba(features)[:, 1] >= model.threshold
