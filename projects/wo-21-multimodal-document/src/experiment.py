"""Run the official FUNSD question-answer link comparison."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from data.download import DATASET_URL, EXPECTED_SHA256
from src.dataset import load_split
from src.evaluation import build_report, save_error_cases
from src.features import (
    build_feature_matrices,
    build_fold_feature_matrices,
    layout_vector,
    text_representation,
)
from src.model import fit_link_model, predict_links
from src.rules import fit_proximity_rule, predict_proximity_rule

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_DIR / "data" / "raw" / "dataset"
RESULTS_DIR = PROJECT_DIR / "results"


def main() -> None:
    """Fit both models on official training documents and evaluate official test."""
    train = load_split(DATASET_DIR, "training_data")
    test = load_split(DATASET_DIR, "testing_data")
    labels = np.asarray([row.linked for row in train], dtype=bool)
    if not labels.any():
        raise ValueError("Training split contains no positive question-answer links")
    train_groups = np.asarray([row.document_id for row in train], dtype=str)
    train_text_rows = [text_representation(row) for row in train]
    train_layout_rows = np.vstack([layout_vector(row) for row in train])
    train_text, test_text, train_layout, test_layout, vectorizer = build_feature_matrices(train, test)
    text_model = fit_link_model(
        train_text,
        labels,
        train_groups,
        uses_layout=False,
        fold_feature_builder=lambda train_indices, validation_indices: build_fold_feature_matrices(
            train_text_rows, train_layout_rows, train_indices, validation_indices, uses_layout=False
        ),
    )
    layout_model = fit_link_model(
        train_layout,
        labels,
        train_groups,
        uses_layout=True,
        fold_feature_builder=lambda train_indices, validation_indices: build_fold_feature_matrices(
            train_text_rows, train_layout_rows, train_indices, validation_indices, uses_layout=True
        ),
    )
    proximity_rule = fit_proximity_rule(train)
    text_predictions = predict_links(text_model, test_text)
    layout_predictions = predict_links(layout_model, test_layout)
    rule_predictions = predict_proximity_rule(test, proximity_rule)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report(test, text_predictions, layout_predictions)
    report["metadata"]["training_candidate_pairs"] = len(train)
    report["metadata"]["training_gold_links"] = int(labels.sum())
    report["metadata"]["training_documents_with_candidate_pairs"] = int(len(np.unique(train_groups)))
    report["metadata"]["training_documents_without_candidate_pairs"] = (
        report["metadata"]["training_split_documents"]
        - report["metadata"]["training_documents_with_candidate_pairs"]
    )
    report["metadata"]["dataset_archive_url"] = DATASET_URL
    report["metadata"]["dataset_archive_sha256"] = EXPECTED_SHA256
    report["metadata"]["official_evaluation_split_documents"] = len(
        list((DATASET_DIR / "testing_data" / "annotations").glob("*.json"))
    )
    report["metadata"]["documents_without_question_answer_candidates"] = (
        report["metadata"]["official_evaluation_split_documents"]
        - report["metadata"]["evaluation_split_documents"]
    )
    report["metadata"]["candidate_document_coverage"] = (
        report["metadata"]["evaluation_split_documents"]
        / report["metadata"]["official_evaluation_split_documents"]
    )
    transitions = save_error_cases(
        RESULTS_DIR / "error_cases.jsonl", test, text_predictions, layout_predictions
    )
    report["error_transition_counts"] = dict(sorted(transitions.items()))
    report["model_config"] = {
        "classifier": "scikit-learn LogisticRegression",
        "C": float(text_model.classifier.C),
        "class_weight": "balanced",
        "text_only_threshold_from_grouped_train_cv": text_model.threshold,
        "text_plus_layout_threshold_from_grouped_train_cv": layout_model.threshold,
        "grouped_train_cv": {
            "document_folds": 5,
            "text_only_precision": text_model.cv_precision,
            "text_only_recall": text_model.cv_recall,
            "text_only_f1": text_model.cv_f1,
            "text_plus_layout_precision": layout_model.cv_precision,
            "text_plus_layout_recall": layout_model.cv_recall,
            "text_plus_layout_f1": layout_model.cv_f1,
            "proximity_rule_precision": proximity_rule.cv_precision,
            "proximity_rule_recall": proximity_rule.cv_recall,
            "proximity_rule_f1": proximity_rule.cv_f1,
        },
        "proximity_rule_max_normalized_distance": proximity_rule.max_normalized_distance,
        "text_features": "word TF-IDF unigram/bigram; fit on train candidates only",
        "layout_features": ["dx", "dy", "abs_dx", "abs_dy", "distance", "same_row", "horizontal_overlap", "answer_below", "width_ratio", "height_ratio"],
        "vocabulary_size": len(vectorizer.vocabulary_),
    }
    rule_true_positive = int(np.sum(np.asarray([row.linked for row in test], dtype=bool) & rule_predictions))
    rule_false_positive = int(np.sum(~np.asarray([row.linked for row in test], dtype=bool) & rule_predictions))
    rule_false_negative = int(np.sum(np.asarray([row.linked for row in test], dtype=bool) & ~rule_predictions))
    rule_denominator = 2 * rule_true_positive + rule_false_positive + rule_false_negative
    report["coordinate_proximity_rule"] = {
        "true_positive_links": rule_true_positive,
        "false_positive_links": rule_false_positive,
        "false_negative_links": rule_false_negative,
        "precision": rule_true_positive / (rule_true_positive + rule_false_positive)
        if rule_true_positive + rule_false_positive else 0.0,
        "recall": rule_true_positive / (rule_true_positive + rule_false_negative)
        if rule_true_positive + rule_false_negative else 0.0,
        "f1": 2 * rule_true_positive / rule_denominator if rule_denominator else 0.0,
    }
    (RESULTS_DIR / "experiment_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
