"""Population stability metrics with explicit missing-value treatment."""

from __future__ import annotations

import numpy as np
import pandas as pd


EPSILON = 1e-6
MISSING_BUCKET = "__MISSING__"


def _psi_from_labels(reference: pd.Series, comparison: pd.Series) -> float:
    """Calculate PSI from aligned bucket labels with epsilon smoothing."""

    labels = reference.unique().tolist()
    labels.extend(label for label in comparison.unique() if label not in labels)
    reference_share = reference.value_counts(normalize=True).reindex(labels, fill_value=0.0)
    comparison_share = comparison.value_counts(normalize=True).reindex(labels, fill_value=0.0)
    reference_share = reference_share.clip(lower=EPSILON)
    comparison_share = comparison_share.clip(lower=EPSILON)
    contributions = (comparison_share - reference_share) * np.log(
        comparison_share / reference_share
    )
    return float(contributions.sum())


def population_stability_index(
    reference: pd.Series,
    comparison: pd.Series,
    bins: int = 10,
) -> float:
    """Compute PSI using reference quantiles and a dedicated missing bucket."""

    if len(reference) == 0 or len(comparison) == 0:
        raise ValueError("PSI inputs must be non-empty")
    numeric = pd.api.types.is_numeric_dtype(reference)
    reference_non_missing = reference.dropna()
    if numeric and reference_non_missing.nunique() > bins:
        quantiles = np.linspace(0.0, 1.0, bins + 1)
        internal = np.unique(reference_non_missing.quantile(quantiles).to_numpy())[1:-1]
        edges = np.concatenate(([-np.inf], internal, [np.inf]))

        def bucket(values: pd.Series) -> pd.Series:
            numeric_values = pd.to_numeric(values, errors="coerce")
            labels = pd.Series(MISSING_BUCKET, index=values.index, dtype="object")
            present = numeric_values.notna()
            labels.loc[present] = np.digitize(
                numeric_values.loc[present].to_numpy(), edges[1:-1], right=True
            ).astype(str)
            return labels

        return _psi_from_labels(bucket(reference), bucket(comparison))

    reference_labels = reference.fillna(MISSING_BUCKET).astype(str)
    comparison_labels = comparison.fillna(MISSING_BUCKET).astype(str)
    return _psi_from_labels(reference_labels, comparison_labels)


def feature_psi_table(
    frame: pd.DataFrame,
    reference_indices: np.ndarray,
    comparison_indices: np.ndarray,
    features: list[str],
    bins: int = 10,
) -> pd.DataFrame:
    """Measure feature-level PSI and missingness for one feature policy."""

    rows: list[dict[str, object]] = []
    reference = frame.iloc[reference_indices]
    comparison = frame.iloc[comparison_indices]
    for feature in features:
        source = "application"
        if feature.startswith("BUREAU_"):
            source = "bureau_aggregate"
        elif feature.startswith("PREV_"):
            source = "previous_aggregate"
        rows.append(
            {
                "feature": feature,
                "source": source,
                "psi": population_stability_index(
                    reference[feature], comparison[feature], bins=bins
                ),
                "reference_missing_rate": float(reference[feature].isna().mean()),
                "comparison_missing_rate": float(comparison[feature].isna().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)


def summarize_psi(table: pd.DataFrame, alert_threshold: float) -> dict[str, float | int]:
    """Summarize a feature PSI table without hiding the upper tail."""

    values = table["psi"]
    return {
        "mean_psi": float(values.mean()),
        "median_psi": float(values.median()),
        "p95_psi": float(values.quantile(0.95)),
        "max_psi": float(values.max()),
        "features": int(len(values)),
        "features_above_0_25": int((values > alert_threshold).sum()),
    }

