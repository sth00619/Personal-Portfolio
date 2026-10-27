"""Text and geometry feature construction for candidate entity links."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer

from src.dataset import PairExample

LAYOUT_FEATURE_NAMES = (
    "dx",
    "dy",
    "abs_dx",
    "abs_dy",
    "distance",
    "same_row",
    "horizontal_overlap",
    "answer_below",
    "width_ratio",
    "height_ratio",
)
MIN_BOX_DIMENSION = 1.0
SAME_ROW_HEIGHT_FACTOR = 1.5
MIN_DOCUMENT_FREQUENCY = 2
TEXT_NGRAM_RANGE = (1, 2)


def text_representation(example: PairExample) -> str:
    """Serialize both entities with role markers for a pairwise text model."""
    return f"QUESTION {example.question.text} ANSWER {example.answer.text}"


def layout_vector(example: PairExample) -> np.ndarray:
    """Return normalized relative geometry for one question-answer pair."""
    qx1, qy1, qx2, qy2 = example.question.box
    ax1, ay1, ax2, ay2 = example.answer.box
    width = max(example.question.page_width, example.answer.page_width, MIN_BOX_DIMENSION)
    height = max(example.question.page_height, example.answer.page_height, MIN_BOX_DIMENSION)
    qcx, qcy = (qx1 + qx2) / 2.0, (qy1 + qy2) / 2.0
    acx, acy = (ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0
    dx, dy = (acx - qcx) / width, (acy - qcy) / height
    qh, ah = max(qy2 - qy1, MIN_BOX_DIMENSION), max(ay2 - ay1, MIN_BOX_DIMENSION)
    qw, aw = max(qx2 - qx1, MIN_BOX_DIMENSION), max(ax2 - ax1, MIN_BOX_DIMENSION)
    horizontal_intersection = max(0.0, min(qx2, ax2) - max(qx1, ax1))
    horizontal_overlap = horizontal_intersection / max(min(qw, aw), 1.0)
    return np.asarray(
        [
            dx,
            dy,
            abs(dx),
            abs(dy),
            float(np.hypot(dx, dy)),
            float(abs(qcy - acy) <= max(qh, ah) * SAME_ROW_HEIGHT_FACTOR),
            horizontal_overlap,
            float(acy > qcy),
            aw / qw,
            ah / qh,
        ],
        dtype=np.float64,
    )


def build_feature_matrices(
    train: list[PairExample], test: list[PairExample]
) -> tuple[csr_matrix, csr_matrix, csr_matrix, csr_matrix, TfidfVectorizer]:
    """Fit training-only TF-IDF and create text-only and text-plus-layout matrices."""
    vectorizer = TfidfVectorizer(
        ngram_range=TEXT_NGRAM_RANGE,
        min_df=MIN_DOCUMENT_FREQUENCY,
        sublinear_tf=True,
    )
    train_text = vectorizer.fit_transform(text_representation(row) for row in train)
    test_text = vectorizer.transform(text_representation(row) for row in test)
    train_layout = csr_matrix(np.vstack([layout_vector(row) for row in train]))
    test_layout = csr_matrix(np.vstack([layout_vector(row) for row in test]))
    return (
        train_text,
        test_text,
        hstack([train_text, train_layout], format="csr"),
        hstack([test_text, test_layout], format="csr"),
        vectorizer,
    )


def build_fold_feature_matrices(
    text_rows: list[str],
    layout_rows: NDArray[np.float64],
    train_indices: NDArray[np.int_],
    validation_indices: NDArray[np.int_],
    uses_layout: bool,
) -> tuple[csr_matrix, csr_matrix]:
    """Fit a fold-local vocabulary and transform only its held-out documents."""
    vectorizer = TfidfVectorizer(
        ngram_range=TEXT_NGRAM_RANGE,
        min_df=MIN_DOCUMENT_FREQUENCY,
        sublinear_tf=True,
    )
    training_text = vectorizer.fit_transform([text_rows[index] for index in train_indices])
    validation_text = vectorizer.transform([text_rows[index] for index in validation_indices])
    if not uses_layout:
        return training_text, validation_text
    training_layout = csr_matrix(layout_rows[train_indices])
    validation_layout = csr_matrix(layout_rows[validation_indices])
    return (
        hstack([training_text, training_layout], format="csr"),
        hstack([validation_text, validation_layout], format="csr"),
    )
