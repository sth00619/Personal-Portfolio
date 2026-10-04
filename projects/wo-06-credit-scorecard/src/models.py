"""WoE logistic scorecard, PDO scaling, and LightGBM challenger."""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from optbinning import OptimalBinning
from sklearn.linear_model import LogisticRegression

from src.data import FEATURES, assert_feature_allowlist

MIN_IV = 0.01
MAX_PREBINS = 10
MIN_BIN_SIZE = 0.05
BINNING_TIME_LIMIT = 5
BASE_SCORE = 600
BASE_GOOD_BAD_ODDS = 20
POINTS_TO_DOUBLE_ODDS = 50
LOGISTIC_MAX_ITER = 1000
RANDOM_STATE = 42


@dataclass
class Scorecard:
    """Fitted training-only WoE bins and a logistic PD model."""

    binners: dict[str, OptimalBinning]
    information_value: dict[str, float]
    selected_features: tuple[str, ...]
    model: LogisticRegression

    def transform(self, frame: pd.DataFrame) -> NDArray[np.float64]:
        """Apply learned bins without fitting to validation data."""
        assert_feature_allowlist(list(frame.columns))
        return np.column_stack(
            [self.binners[name].transform(frame[name].to_numpy(), metric="woe") for name in self.selected_features]
        ).astype(float)

    def predict_pd(self, frame: pd.DataFrame) -> NDArray[np.float64]:
        """Return estimated probability of default."""
        return self.model.predict_proba(self.transform(frame))[:, 1].astype(float)

    def score(self, frame: pd.DataFrame) -> NDArray[np.float64]:
        """Convert PD to points with higher score indicating lower risk."""
        return pd_to_points(self.predict_pd(frame))


def pd_to_points(probability: NDArray[np.float64]) -> NDArray[np.float64]:
    """Scale good/bad odds so doubling good odds adds PDO points."""
    clipped = np.clip(probability, 1e-9, 1 - 1e-9)
    factor = POINTS_TO_DOUBLE_ODDS / np.log(2)
    offset = BASE_SCORE - factor * np.log(BASE_GOOD_BAD_ODDS)
    return (offset + factor * np.log((1 - clipped) / clipped)).astype(float)


def fit_scorecard(frame: pd.DataFrame, target: NDArray[np.int_]) -> Scorecard:
    """Learn WoE bins and IV on training applications only."""
    assert_feature_allowlist(list(frame.columns))
    binners: dict[str, OptimalBinning] = {}
    iv_values: dict[str, float] = {}
    for name in FEATURES:
        binner = OptimalBinning(
            name=name, dtype="numerical", max_n_prebins=MAX_PREBINS,
            min_bin_size=MIN_BIN_SIZE, solver="cp", time_limit=BINNING_TIME_LIMIT,
        )
        binner.fit(frame[name].to_numpy(), target)
        binner.binning_table.build()
        binners[name] = binner
        iv_values[name] = float(binner.binning_table.iv)
    selected = tuple(name for name in FEATURES if iv_values[name] >= MIN_IV)
    if not selected:
        selected = (max(FEATURES, key=iv_values.get),)
    transformed = np.column_stack(
        [binners[name].transform(frame[name].to_numpy(), metric="woe") for name in selected]
    )
    model = LogisticRegression(max_iter=LOGISTIC_MAX_ITER, random_state=RANDOM_STATE)
    model.fit(transformed, target)
    return Scorecard(binners, iv_values, selected, model)


def fit_challenger(
    frame: pd.DataFrame, target: NDArray[np.int_], parameters: dict[str, int | float]
) -> lgb.LGBMClassifier:
    """Train LightGBM on the same raw application-time feature set."""
    assert_feature_allowlist(list(frame.columns))
    model = lgb.LGBMClassifier(
        objective="binary", random_state=RANDOM_STATE, verbosity=-1, n_jobs=2,
        **parameters,
    )
    model.fit(frame, target)
    return model
