"""LightGBM point and quantile model fitting."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .config import ExperimentConfig


IGNORED_COLUMNS = ("target", "item_id")


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Return model inputs while excluding identifiers and labels."""

    return [column for column in frame.columns if column not in IGNORED_COLUMNS]


def _base_params(config: ExperimentConfig) -> dict[str, object]:
    """Build deterministic LightGBM parameters shared by every model."""

    return {
        "n_estimators": config.n_estimators,
        "learning_rate": config.learning_rate,
        "num_leaves": config.num_leaves,
        "min_child_samples": config.min_child_samples,
        "subsample": 1.0,
        "colsample_bytree": 1.0,
        "reg_lambda": 0.1,
        "random_state": config.random_seed,
        "n_jobs": -1,
        "verbosity": -1,
    }


def fit_point_model(train: pd.DataFrame, config: ExperimentConfig) -> LGBMRegressor:
    """Fit the squared-error point forecast baseline."""

    model = LGBMRegressor(objective="regression_l2", **_base_params(config))
    columns = feature_columns(train)
    model.fit(train[columns], train["target"], categorical_feature=["item_code"])
    return model


def fit_quantile_models(
    train: pd.DataFrame,
    quantiles: Sequence[float],
    config: ExperimentConfig,
) -> dict[float, LGBMRegressor]:
    """Fit one independent LightGBM model for each requested quantile."""

    columns = feature_columns(train)
    models: dict[float, LGBMRegressor] = {}
    for quantile in quantiles:
        model = LGBMRegressor(
            objective="quantile",
            alpha=quantile,
            **_base_params(config),
        )
        model.fit(train[columns], train["target"], categorical_feature=["item_code"])
        models[quantile] = model
    return models


def predict_point(model: LGBMRegressor, frame: pd.DataFrame) -> np.ndarray:
    """Predict non-negative demand from a point model."""

    prediction = model.predict(frame[feature_columns(frame)])
    return np.clip(np.asarray(prediction, dtype=float), 0.0, None)


def predict_quantiles(
    models: dict[float, LGBMRegressor],
    frame: pd.DataFrame,
    quantiles: Sequence[float],
) -> np.ndarray:
    """Predict a non-negative observation-by-quantile matrix."""

    columns = feature_columns(frame)
    matrix = np.column_stack(
        [np.clip(models[q].predict(frame[columns]), 0.0, None) for q in quantiles]
    )
    return np.asarray(matrix, dtype=float)

