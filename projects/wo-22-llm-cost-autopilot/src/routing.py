"""Train a supervised quality-risk router and evaluate decision cutoffs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit

from .dataset import Example
from .scoring import answer_f1


EASY_F1_FLOOR = 0.80
SPLIT_SEED = 22_021
ROUTE_THRESHOLDS = (0.20, 0.35, 0.50, 0.65, 0.80, 0.95)


@dataclass
class Router:
    """Question-text vectorizer and model for low-tier answer adequacy."""

    vectorizer: TfidfVectorizer
    classifier: LogisticRegression

    def predict_easy_probability(self, questions: list[str]) -> NDArray[np.float64]:
        """Return the estimated chance that the economy output clears the F1 floor."""
        matrix = self.vectorizer.transform(questions)
        positive_column = list(self.classifier.classes_).index(1)
        return self.classifier.predict_proba(matrix)[:, positive_column]


def group_split(examples: list[Example]) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Split by article title so one article cannot leak across train and test."""
    indices = np.arange(len(examples))
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SPLIT_SEED)
    train, test = next(splitter.split(indices, groups=[item.title for item in examples]))
    return train.astype(np.int64), test.astype(np.int64)


def fit_router(examples: list[Example], train_indices: NDArray[np.int64]) -> Router:
    """Fit a quality-risk classifier using only training-article answer outcomes."""
    train_examples = [examples[int(index)] for index in train_indices]
    labels = np.asarray([
        int(answer_f1(item.answer_a, item.answers, item.impossible) >= EASY_F1_FLOOR)
        for item in train_examples
    ], dtype=np.int64)
    if len(np.unique(labels)) != 2:
        raise ValueError("Router training split must contain easy and hard examples")
    vectorizer = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=2, max_features=60_000,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([item.question for item in train_examples])
    classifier = LogisticRegression(
        C=1.0, class_weight="balanced", max_iter=1_000, random_state=SPLIT_SEED,
    )
    classifier.fit(matrix, labels)
    return Router(vectorizer, classifier)


def true_easy(item: Example) -> bool:
    """Return the held-out label used only to categorize router errors."""
    return answer_f1(item.answer_a, item.answers, item.impossible) >= EASY_F1_FLOOR
