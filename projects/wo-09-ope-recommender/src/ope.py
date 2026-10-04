"""Position-standardized OBP estimates and stratified bootstrap intervals."""

from __future__ import annotations

from typing import Any

import numpy as np
from obp.ope import (
    DirectMethod,
    DoublyRobust,
    InverseProbabilityWeighting,
    OffPolicyEvaluation,
    SelfNormalizedInverseProbabilityWeighting,
)


ESTIMATOR_NAMES = ("dm", "ipw", "snipw", "dr")
POSITIONS = 3
BOOTSTRAP_SAMPLES = 400
BOOTSTRAP_SEED = 481


def _slice_feedback(feedback: dict[str, Any], mask: np.ndarray) -> dict[str, Any]:
    """Select one position's logged rows for an OBP estimator call."""
    n = len(feedback["action"])
    sliced: dict[str, Any] = {}
    for key, value in feedback.items():
        if isinstance(value, np.ndarray) and value.ndim > 0 and value.shape[0] == n:
            sliced[key] = value[mask]
        else:
            sliced[key] = value
    sliced["n_rounds"] = int(mask.sum())
    return sliced


def estimate_policy(
    feedback: dict[str, Any],
    action_dist: np.ndarray,
    q_hat: np.ndarray,
    n_bootstrap: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    """Use OBP points and resample rounds within each position for CIs."""
    action = np.asarray(feedback["action"], dtype=int)
    position = np.asarray(feedback["position"], dtype=int)
    reward = np.asarray(feedback["reward"], dtype=float)
    pscore = np.asarray(feedback["pscore"], dtype=float)
    n = len(action)
    if action_dist.shape != q_hat.shape or action_dist.shape[0] != n:
        raise ValueError("Policy and reward arrays must match feedback dimensions")
    if np.any(pscore <= 0) or set(np.unique(position)) != set(range(POSITIONS)):
        raise ValueError("Positive propensities and all positions are required")
    if not np.allclose(action_dist.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("Each position must have a normalized action distribution")

    row = np.arange(n)
    pi = action_dist[row, :, position]
    q_position = q_hat[row, :, position]
    dm_row = np.sum(pi * q_position, axis=1)
    weight = pi[row, action] / pscore
    ipw_row = weight * reward
    dr_row = dm_row + weight * (reward - q_position[row, action])

    names = [DirectMethod(), InverseProbabilityWeighting(),
             SelfNormalizedInverseProbabilityWeighting(), DoublyRobust()]
    by_position: dict[int, dict[str, float]] = {}
    indices: dict[int, np.ndarray] = {}
    for pos in range(POSITIONS):
        mask = position == pos
        indices[pos] = np.flatnonzero(mask)
        evaluator = OffPolicyEvaluation(
            bandit_feedback=_slice_feedback(feedback, mask), ope_estimators=names
        )
        values = evaluator.estimate_policy_values(
            action_dist=action_dist[mask],
            estimated_rewards_by_reg_model=q_hat[mask],
        )
        by_position[pos] = {name: float(value) for name, value in values.items()}
        local = indices[pos]
        checks = {
            "dm": float(dm_row[local].mean()),
            "ipw": float(ipw_row[local].mean()),
            "snipw": float(ipw_row[local].sum() / weight[local].sum()),
            "dr": float(dr_row[local].mean()),
        }
        for name, value in checks.items():
            if not np.isclose(by_position[pos][name], value, rtol=1e-5, atol=1e-8):
                raise AssertionError(f"OBP mismatch for {name} at position {pos}")

    estimates = {
        name: float(np.mean([by_position[pos][name] for pos in range(POSITIONS)]))
        for name in ESTIMATOR_NAMES
    }
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    bootstrap = {name: np.empty(n_bootstrap, dtype=float) for name in ESTIMATOR_NAMES}
    for iteration in range(n_bootstrap):
        totals = {name: 0.0 for name in ESTIMATOR_NAMES}
        for pos in range(POSITIONS):
            local = indices[pos]
            sample = rng.choice(local, size=len(local), replace=True)
            totals["dm"] += float(dm_row[sample].mean()) / POSITIONS
            totals["ipw"] += float(ipw_row[sample].mean()) / POSITIONS
            totals["snipw"] += float(ipw_row[sample].sum() / weight[sample].sum()) / POSITIONS
            totals["dr"] += float(dr_row[sample].mean()) / POSITIONS
        for name in ESTIMATOR_NAMES:
            bootstrap[name][iteration] = totals[name]
    intervals = {
        name: [float(np.quantile(bootstrap[name], 0.025)),
               float(np.quantile(bootstrap[name], 0.975))]
        for name in ESTIMATOR_NAMES
    }
    ess = float(weight.sum() ** 2 / np.square(weight).sum())
    return {
        "estimates": estimates,
        "intervals": intervals,
        "per_position": by_position,
        "diagnostics": {
            "logged_rows": n,
            "clicked_rows": int(reward.sum()),
            "min_pscore": float(pscore.min()),
            "max_weight": float(weight.max()),
            "p99_weight": float(np.quantile(weight, 0.99)),
            "effective_sample_size": ess,
            "zero_weight_fraction": float(np.mean(weight == 0)),
            "bootstrap_samples": n_bootstrap,
        },
    }
