"""Application-time feature allowlist and monthly sampling."""

from pathlib import Path

import pandas as pd

FEATURES = ("revenue", "dti_n", "loan_amnt", "fico_n", "experience_c")
TARGET = "Default"
MONTH = "issue_d"
REQUIRED = (*FEATURES, TARGET, MONTH)
POST_DECISION_FIELDS = frozenset(
    {"loan_status", "last_pymnt_amnt", "recoveries", "total_rec_prncp", "grade", "int_rate"}
)
DATE_FORMAT = "%b-%Y"
RANDOM_STATE = 42


def assert_feature_allowlist(columns: list[str] | tuple[str, ...]) -> None:
    """Reject target, time, identifier, and unknown fields as model inputs."""
    unexpected = set(columns) - set(FEATURES)
    if unexpected or not columns or len(set(columns)) != len(columns):
        raise ValueError(f"Only application-time allowlisted features are permitted: {unexpected}")
    if set(columns) & POST_DECISION_FIELDS:
        raise ValueError("Post-decision fields are forbidden")


def load_applications(
    path: Path, start_month: str, end_month: str, monthly_cap: int
) -> pd.DataFrame:
    """Load only allowed fields and take a deterministic per-month sample."""
    if monthly_cap < 100:
        raise ValueError("monthly_cap must be at least 100")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = set(REQUIRED) - set(header)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    frame = pd.read_csv(path, usecols=list(REQUIRED), low_memory=False)
    frame[MONTH] = pd.to_datetime(frame[MONTH], format=DATE_FORMAT, errors="coerce")
    frame[TARGET] = pd.to_numeric(frame[TARGET], errors="coerce")
    for feature in FEATURES:
        frame[feature] = pd.to_numeric(frame[feature], errors="coerce")
    frame = frame.dropna(subset=[MONTH, TARGET])
    frame = frame[frame[TARGET].isin([0, 1])].copy()
    frame["month"] = frame[MONTH].dt.to_period("M").astype(str)
    frame = frame[frame["month"].between(start_month, end_month)]
    sampled = pd.concat(
        group.sample(n=min(len(group), monthly_cap), random_state=RANDOM_STATE)
        for _, group in frame.groupby("month", sort=True)
    )
    sampled = sampled.reset_index(drop=True).sort_values("month").reset_index(drop=True)
    if sampled.empty:
        raise ValueError("No applications remain in the requested month range")
    return sampled


def assert_temporal_split(train: pd.DataFrame, test: pd.DataFrame) -> None:
    """Ensure each validation vintage follows all training vintages."""
    if train.empty or test.empty or train["month"].max() >= test["month"].min():
        raise ValueError("Temporal split overlaps or is out of order")


def expanding_month_splits(
    frame: pd.DataFrame, validation_months: int, min_train_months: int
) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    """Create expanding monthly train sets and one-month validation sets."""
    months = sorted(frame["month"].unique().tolist())
    if validation_months < 2 or len(months) < min_train_months + validation_months:
        raise ValueError("Insufficient months for the requested expanding validation")
    folds = []
    for month in months[-validation_months:]:
        train = frame.loc[frame["month"] < month].copy()
        test = frame.loc[frame["month"] == month].copy()
        assert_temporal_split(train, test)
        if train["month"].nunique() < min_train_months:
            raise ValueError("Training history is shorter than required")
        folds.append((month, train, test))
    return folds
