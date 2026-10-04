"""Discrimination and population-stability measurements."""

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import roc_auc_score

PSI_WARNING = 0.10
PSI_RETRAIN = 0.25
PSI_EPSILON = 1e-6
PSI_QUANTILES = 10


def auc_gini(y_true: NDArray[np.int_], probability: NDArray[np.float64]) -> tuple[float, float]:
    """Return ROC AUC and Gini=2*AUC-1 for default as the positive class."""
    if len(np.unique(y_true)) != 2:
        raise ValueError("AUC requires both default and non-default examples")
    auc = float(roc_auc_score(y_true, probability))
    return auc, 2 * auc - 1


def population_stability_index(
    reference: NDArray[np.float64], current: NDArray[np.float64]
) -> float:
    """Compute PSI with quantile bins fixed on the training distribution."""
    if len(reference) == 0 or len(current) == 0:
        raise ValueError("PSI requires nonempty samples")
    if not np.isfinite(reference).all() or not np.isfinite(current).all():
        raise ValueError("PSI requires finite values")
    quantiles = np.linspace(0, 1, PSI_QUANTILES + 1)
    interior = np.unique(np.quantile(reference, quantiles)[1:-1])
    edges = np.r_[-np.inf, interior, np.inf]
    if len(edges) < 3:
        return 0.0 if np.all(current == reference[0]) else float("inf")
    reference_share = np.histogram(reference, bins=edges)[0] / len(reference)
    current_share = np.histogram(current, bins=edges)[0] / len(current)
    reference_share = np.clip(reference_share, PSI_EPSILON, None)
    current_share = np.clip(current_share, PSI_EPSILON, None)
    return float(np.sum((current_share - reference_share) * np.log(current_share / reference_share)))


def psi_signal(psi: float) -> str:
    """Map a conventional heuristic PSI band to a review signal."""
    if psi > PSI_RETRAIN:
        return "RETRAIN_REVIEW"
    if psi >= PSI_WARNING:
        return "INVESTIGATE"
    return "STABLE"
