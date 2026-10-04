"""Two-stage recommendation and reward modeling on Open Bandit Dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from obp.dataset import OpenBanditDataset
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"
CAMPAIGN = "men"
BEHAVIOR = "random"
N_POSITIONS = 3
FIT_FRACTION = 0.55
TRAIN_FRACTION = 0.70
TOP_CANDIDATES = 10
TOP_RANKED = 3
EXPLORATION = 0.05
POPULARITY_SMOOTHING = 200.0
POPULARITY_WEIGHT = 0.5
CF_WEIGHT = 0.5
SCORE_CHUNK_ROUNDS = 2000
POLICY_FIT_SEED = 73
POLICY_DIRICHLET_PRIOR = 0.5
MATCHED_TIME_CHUNK = 200000
MODEL_TREES = 100
MODEL_LEAVES = 15
MODEL_MIN_CHILD = 200
MODEL_SEED = 37
FEATURE_NAMES = (
    "user_0", "user_1", "user_2", "user_3", "item_id",
    "item_numeric", "item_category_1", "item_category_2", "item_category_3",
    "position", "historical_affinity",
)
CATEGORICAL_INDICES = (0, 1, 2, 3, 4, 6, 7, 8, 9)


@dataclass
class FeatureStore:
    """Compact context and item features for all candidate actions."""

    user_codes: np.ndarray
    affinity: np.ndarray
    item_numeric: np.ndarray
    item_categories: np.ndarray

    def matrix(
        self, rows: np.ndarray, actions: np.ndarray, positions: np.ndarray,
        include_position: bool = True,
    ) -> np.ndarray:
        """Build a pointwise reward model matrix without outcome leakage."""
        if not (len(rows) == len(actions) == len(positions)):
            raise ValueError("Feature index lengths must match")
        columns = [
            *[self.user_codes[rows, idx] for idx in range(4)],
            actions, self.item_numeric[actions],
            *[self.item_categories[actions, idx] for idx in range(3)],
        ]
        if include_position:
            columns.append(positions)
        columns.append(self.affinity[rows, actions])
        return np.column_stack(columns).astype(np.float32, copy=False)


@dataclass
class CalibratedModel:
    """Pointwise LightGBM model with held-out Platt calibration."""

    estimator: lgb.LGBMClassifier
    slope: float
    intercept: float
    include_position: bool

    def predict(
        self, store: FeatureStore, rows: np.ndarray,
        actions: np.ndarray, positions: np.ndarray,
    ) -> np.ndarray:
        """Predict calibrated click probability for arbitrary item-slot pairs."""
        matrix = store.matrix(rows, actions, positions, self.include_position)
        raw = np.clip(self.estimator.predict_proba(matrix)[:, 1], 1e-7, 1 - 1e-7)
        logit = np.log(raw / (1 - raw))
        return expit(self.slope * logit + self.intercept)


def load_dataset() -> tuple[OpenBanditDataset, dict[str, Any], dict[str, Any]]:
    """Load and chronologically split official Random Men bandit feedback."""
    dataset = OpenBanditDataset(
        behavior_policy=BEHAVIOR, campaign=CAMPAIGN, data_path=RAW
    )
    if dataset.n_actions != 34 or dataset.len_list != N_POSITIONS:
        raise ValueError("Unexpected campaign action or position dimensions")
    train, evaluation = dataset.obtain_batch_bandit_feedback(
        test_size=1 - TRAIN_FRACTION, is_timeseries_split=True
    )
    if np.any(dataset.pscore <= 0):
        raise ValueError("OPE requires positive logging propensities")
    return dataset, train, evaluation


def encode_features(dataset: OpenBanditDataset, fit_end: int) -> FeatureStore:
    """Encode user categories with fitting-window vocabulary only."""
    data = dataset.data
    user_codes = np.empty((len(data), 4), dtype=np.int32)
    for idx in range(4):
        column = f"user_feature_{idx}"
        categories = pd.Index(data[column].iloc[:fit_end].astype(str).unique())
        user_codes[:, idx] = pd.Categorical(
            data[column].astype(str), categories=categories
        ).codes.astype(np.int32)
    affinity_columns = [f"user-item_affinity_{idx}" for idx in range(dataset.n_actions)]
    affinity = data[affinity_columns].to_numpy(dtype=np.float32, copy=True)
    items = dataset.item_context.sort_values("item_id").reset_index(drop=True)
    if not np.array_equal(items["item_id"].to_numpy(), np.arange(dataset.n_actions)):
        raise ValueError("Item feature rows must cover consecutive action IDs")
    item_numeric = items["item_feature_0"].to_numpy(dtype=np.float32)
    item_categories = np.column_stack([
        pd.Categorical(items[f"item_feature_{idx}"].astype(str)).codes
        for idx in range(1, 4)
    ]).astype(np.int32)
    return FeatureStore(user_codes, affinity, item_numeric, item_categories)


def fit_calibrated_model(
    store: FeatureStore, feedback: dict[str, Any],
    fit_end: int, calibration_end: int, include_position: bool,
) -> CalibratedModel:
    """Fit a reward model and calibrate it on later Random-policy rows."""
    action = np.asarray(feedback["action"])
    position = np.asarray(feedback["position"])
    reward = np.asarray(feedback["reward"])
    fit_rows = np.arange(fit_end)
    calibration_rows = np.arange(fit_end, calibration_end)
    x_fit = store.matrix(
        fit_rows, action[fit_rows], position[fit_rows], include_position
    )
    categorical = [idx for idx in CATEGORICAL_INDICES if include_position or idx != 9]
    estimator = lgb.LGBMClassifier(
        n_estimators=MODEL_TREES, learning_rate=0.045,
        num_leaves=MODEL_LEAVES, max_depth=5,
        min_child_samples=MODEL_MIN_CHILD, verbosity=-1,
        random_state=MODEL_SEED, n_jobs=4,
    )
    estimator.fit(x_fit, reward[fit_rows], categorical_feature=categorical)
    x_cal = store.matrix(
        calibration_rows, action[calibration_rows],
        position[calibration_rows], include_position,
    )
    raw = np.clip(estimator.predict_proba(x_cal)[:, 1], 1e-7, 1 - 1e-7)
    logits = np.log(raw / (1 - raw)).reshape(-1, 1)
    calibrator = LogisticRegression(C=10.0, max_iter=1000)
    calibrator.fit(logits, reward[calibration_rows])
    return CalibratedModel(
        estimator, float(calibrator.coef_[0, 0]),
        float(calibrator.intercept_[0]), include_position,
    )


def score_all_actions(
    model: CalibratedModel, store: FeatureStore,
    start: int, stop: int, n_actions: int,
) -> np.ndarray:
    """Score every item and position for held-out contexts in bounded chunks."""
    n = stop - start
    q = np.empty((n, n_actions, N_POSITIONS), dtype=np.float32)
    action_template = np.repeat(np.arange(n_actions), N_POSITIONS)
    position_template = np.tile(np.arange(N_POSITIONS), n_actions)
    for offset in range(0, n, SCORE_CHUNK_ROUNDS):
        upper = min(offset + SCORE_CHUNK_ROUNDS, n)
        count = upper - offset
        rows = np.repeat(np.arange(start + offset, start + upper),
                         n_actions * N_POSITIONS)
        actions = np.tile(action_template, count)
        positions = np.tile(position_template, count)
        q[offset:upper] = model.predict(store, rows, actions, positions).reshape(
            count, n_actions, N_POSITIONS
        )
    return q


def candidate_scores(
    store: FeatureStore, train_action: np.ndarray,
    train_reward: np.ndarray, train_end: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Combine smoothed item popularity and item-item co-affinity CF."""
    n_actions = store.affinity.shape[1]
    impressions = np.bincount(train_action, minlength=n_actions)
    clicks = np.bincount(train_action, weights=train_reward, minlength=n_actions)
    global_ctr = float(train_reward.mean())
    popularity = (clicks + POPULARITY_SMOOTHING * global_ctr) / (
        impressions + POPULARITY_SMOOTHING
    )
    pop_range = np.ptp(popularity)
    pop_score = (popularity - popularity.min()) / max(pop_range, 1e-12)

    historical = (store.affinity[:train_end] > 0).astype(np.float32)
    cooccurrence = historical.T @ historical
    norms = np.sqrt(np.maximum(np.diag(cooccurrence), 0))
    similarity = cooccurrence / np.maximum(np.outer(norms, norms), 1e-12)
    np.fill_diagonal(similarity, 0.0)
    cf_score = store.affinity[train_end:] @ similarity
    cf_score /= np.maximum(cf_score.max(axis=1, keepdims=True), 1e-12)
    hybrid = POPULARITY_WEIGHT * pop_score[None, :] + CF_WEIGHT * cf_score
    diagnostic = {
        "cf_context_coverage": float(np.mean(np.any(store.affinity[train_end:] > 0, axis=1))),
        "nonzero_similarity_pairs": int(np.count_nonzero(similarity)),
        "train_global_ctr": global_ctr,
    }
    return hybrid, pop_score, diagnostic


def top_candidates(
    hybrid_scores: np.ndarray, pop_scores: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return hybrid and popularity-only top-N candidate lists."""
    hybrid = np.argsort(-hybrid_scores, axis=1, kind="stable")[:, :TOP_CANDIDATES]
    popular = np.tile(
        np.argsort(-pop_scores, kind="stable")[:TOP_CANDIDATES],
        (len(hybrid), 1),
    )
    return hybrid, popular


def rerank(candidates: np.ndarray, q_hat: np.ndarray) -> np.ndarray:
    """Order retrieved candidates by position-averaged predicted click rate."""
    candidate_q = np.take_along_axis(
        q_hat.mean(axis=2), candidates, axis=1
    )
    order = np.argsort(-candidate_q, axis=1, kind="stable")
    ranked = np.take_along_axis(candidates, order, axis=1)
    return ranked[:, :TOP_RANKED]


def epsilon_slate_policy(
    ranked: np.ndarray, n_actions: int,
) -> np.ndarray:
    """Mix the top-three slate with uniform random slates for support."""
    n = len(ranked)
    action_dist = np.full(
        (n, n_actions, N_POSITIONS),
        EXPLORATION / n_actions, dtype=np.float32,
    )
    rows = np.arange(n)
    for pos in range(N_POSITIONS):
        action_dist[rows, ranked[:, pos], pos] += 1 - EXPLORATION
    return action_dist


def logged_ranking_metrics(
    action: np.ndarray, position: np.ndarray, reward: np.ndarray,
    candidates: np.ndarray, ranked: np.ndarray,
) -> dict[str, float]:
    """Evaluate clicked-item recall and single-positive nDCG by position."""
    if len(action) != len(candidates) or len(action) != len(ranked):
        raise ValueError("Ranking arrays must align to logged rows")
    recall_by_position: list[float] = []
    ndcg_by_position: list[float] = []
    for pos in range(N_POSITIONS):
        clicked = (position == pos) & (reward > 0)
        if not np.any(clicked):
            raise ValueError(f"No clicked rows in position {pos}")
        items = action[clicked]
        candidate_hits = np.any(candidates[clicked] == items[:, None], axis=1)
        matches = ranked[clicked] == items[:, None]
        discounts = 1.0 / np.log2(np.arange(TOP_RANKED) + 2)
        ndcg = np.sum(matches * discounts[None, :], axis=1)
        recall_by_position.append(float(candidate_hits.mean()))
        ndcg_by_position.append(float(ndcg.mean()))
    return {
        "recall_at_10": float(np.mean(recall_by_position)),
        "ndcg_at_3": float(np.mean(ndcg_by_position)),
        "recall_by_position": recall_by_position,
        "ndcg_by_position": ndcg_by_position,
        "clicked_logged_rows": int(reward.sum()),
    }


def model_diagnostics(
    aware: CalibratedModel, blind: CalibratedModel,
    store: FeatureStore, feedback: dict[str, Any], eval_start: int,
) -> dict[str, float]:
    """Compare position-aware and position-blind held-out reward fits."""
    rows = np.arange(eval_start, store.affinity.shape[0])
    action = np.asarray(feedback["action"])
    position = np.asarray(feedback["position"])
    reward = np.asarray(feedback["reward"])
    aware_p = aware.predict(store, rows, action, position)
    blind_p = blind.predict(store, rows, action, position)
    return {
        "aware_brier": float(brier_score_loss(reward, aware_p)),
        "blind_brier": float(brier_score_loss(reward, blind_p)),
        "aware_auc": float(roc_auc_score(reward, aware_p)),
        "blind_auc": float(roc_auc_score(reward, blind_p)),
        "observed_ctr": float(reward.mean()),
        "aware_mean_prediction": float(aware_p.mean()),
        "blind_mean_prediction": float(blind_p.mean()),
    }


def reconstruct_bts_policy(
    threshold: str, eval_timestamps: pd.Series,
    n_actions: int, prior_distribution: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any], dict[str, float]]:
    """Fit hourly BTS action marginals and reserve independent clicks for truth."""
    path = RAW / "bts" / CAMPAIGN / f"{CAMPAIGN}.csv"
    rng = np.random.default_rng(POLICY_FIT_SEED)
    fit_counts: dict[str, np.ndarray] = {}
    holdout_counts: dict[str, np.ndarray] = {}
    counts = np.zeros(N_POSITIONS, dtype=np.int64)
    clicks = np.zeros(N_POSITIONS, dtype=np.int64)
    for chunk in pd.read_csv(
        path, usecols=["timestamp", "item_id", "position", "click"],
        chunksize=MATCHED_TIME_CHUNK,
    ):
        selected = chunk.loc[chunk["timestamp"] >= threshold].copy()
        if selected.empty:
            continue
        selected["hour"] = selected["timestamp"].str.slice(0, 13)
        fit_mask = rng.random(len(selected)) < 0.5
        fit = selected.loc[fit_mask]
        holdout = selected.loc[~fit_mask]
        for records, target in ((fit, fit_counts), (holdout, holdout_counts)):
            grouped = records.groupby(["hour", "item_id", "position"]).size()
            for (hour, item, pos), count in grouped.items():
                matrix = target.setdefault(
                    str(hour), np.zeros((n_actions, N_POSITIONS), dtype=np.int64)
                )
                matrix[int(item), int(pos) - 1] += int(count)
        for pos in range(N_POSITIONS):
            local = holdout.loc[holdout["position"] == pos + 1, "click"]
            counts[pos] += len(local)
            clicks[pos] += int(local.sum())

    all_fit = sum(fit_counts.values(), np.zeros((n_actions, N_POSITIONS), dtype=np.int64))

    def probabilities(action_counts: np.ndarray) -> np.ndarray:
        """Smooth observed action frequencies into position-specific policies."""
        return (
            (action_counts + POLICY_DIRICHLET_PRIOR) /
            (action_counts.sum(axis=0, keepdims=True) + POLICY_DIRICHLET_PRIOR * n_actions)
        ).astype(np.float32)

    global_policy = probabilities(all_fit)
    by_hour = {hour: probabilities(matrix) for hour, matrix in fit_counts.items()}
    eval_hours = eval_timestamps.astype(str).str.slice(0, 13).to_numpy()
    action_dist = np.empty((len(eval_hours), n_actions, N_POSITIONS), dtype=np.float32)
    for hour in np.unique(eval_hours):
        action_dist[eval_hours == hour] = by_hour.get(str(hour), global_policy)

    fit_tv_total = prior_tv_total = sample_total = 0.0
    for hour, heldout in holdout_counts.items():
        denominator = heldout.sum(axis=0)
        actual = heldout / np.maximum(denominator[None, :], 1)
        fit_tv = np.abs(by_hour.get(hour, global_policy) - actual).sum(axis=0) / 2
        prior_tv = np.abs(prior_distribution - actual).sum(axis=0) / 2
        fit_tv_total += float(np.dot(fit_tv, denominator))
        prior_tv_total += float(np.dot(prior_tv, denominator))
        sample_total += float(denominator.sum())

    rate = clicks / counts
    standardized = float(rate.mean())
    variance = float(np.sum(rate * (1 - rate) / counts) / (N_POSITIONS**2))
    standard_error = float(np.sqrt(variance))
    factual = {
        "rows": int(counts.sum()), "clicks": int(clicks.sum()),
        "position_rows": counts.tolist(), "position_clicks": clicks.tolist(),
        "position_rates": rate.tolist(),
        "raw_rate": float(clicks.sum() / counts.sum()),
        "standardized_rate": standardized,
        "normal_95_ci": [max(0.0, standardized - 1.96 * standard_error),
                         standardized + 1.96 * standard_error],
    }
    diagnostics = {
        "policy_fit_rows": int(all_fit.sum()),
        "truth_rows": int(counts.sum()),
        "hour_bins": len(by_hour),
        "fit_vs_holdout_weighted_tv": fit_tv_total / sample_total,
        "fixed_prior_vs_holdout_weighted_tv": prior_tv_total / sample_total,
        "dirichlet_pseudocount_per_action": POLICY_DIRICHLET_PRIOR,
    }
    return action_dist, factual, diagnostics
