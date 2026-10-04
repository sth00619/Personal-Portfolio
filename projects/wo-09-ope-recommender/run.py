"""Run the fixed WO-09 training, recommendation, and OPE benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from obp.policy import BernoulliTS

from data.download import MEMBERS, verify_local
from src.experiment import (
    CAMPAIGN, EXPLORATION, FIT_FRACTION, N_POSITIONS, RESULTS,
    TOP_CANDIDATES, TOP_RANKED, TRAIN_FRACTION,
    candidate_scores, encode_features, epsilon_slate_policy,
    fit_calibrated_model, load_dataset, reconstruct_bts_policy,
    logged_ranking_metrics, model_diagnostics, rerank,
    score_all_actions, top_candidates,
)
from src.ope import ESTIMATOR_NAMES, estimate_policy


BTS_SIMULATIONS = 100000
MODEL_OUTPUT = RESULTS / "report.json"
METHOD_LABELS = {"dm": "DM", "ipw": "IPS", "snipw": "SNIPS", "dr": "DR"}


def save_tables(report: dict[str, Any]) -> None:
    """Write compact machine-readable Ship Gate tables."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    truth = report["observed_bts"]["standardized_rate"]
    benchmark = report["bts_benchmark"]
    pd.DataFrame([
        {
            "estimator": METHOD_LABELS[name],
            "estimate": benchmark["estimates"][name],
            "ci_lower": benchmark["intervals"][name][0],
            "ci_upper": benchmark["intervals"][name][1],
            "observed_bts": truth,
            "absolute_error": abs(benchmark["estimates"][name] - truth),
        }
        for name in ESTIMATOR_NAMES
    ]).to_csv(RESULTS / "ope_benchmark.csv", index=False)
    new_policy = report["new_policy_ope"]
    pd.DataFrame([
        {
            "estimator": METHOD_LABELS[name],
            "estimate": new_policy["estimates"][name],
            "ci_lower": new_policy["intervals"][name][0],
            "ci_upper": new_policy["intervals"][name][1],
        }
        for name in ESTIMATOR_NAMES
    ]).to_csv(RESULTS / "new_policy_ope.csv", index=False)
    pd.DataFrame([
        {"pipeline": name, **metrics}
        for name, metrics in report["ranking_metrics"].items()
    ]).to_csv(RESULTS / "ranking_metrics.csv", index=False)
    MODEL_OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")


def save_plots(report: dict[str, Any]) -> None:
    """Plot OPE intervals against observed BTS and two-stage ranking metrics."""
    benchmark = report["bts_benchmark"]
    names = list(ESTIMATOR_NAMES)
    estimates = np.array([benchmark["estimates"][name] for name in names])
    lower = np.array([benchmark["intervals"][name][0] for name in names])
    upper = np.array([benchmark["intervals"][name][1] for name in names])
    truth = report["observed_bts"]["standardized_rate"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        np.arange(len(names)), estimates * 100,
        yerr=np.vstack(((estimates - lower) * 100, (upper - estimates) * 100)),
        fmt="o", capsize=5, label="OPE estimate, stratified bootstrap 95% CI",
    )
    ax.axhline(truth * 100, color="black", linestyle="--", label="Observed BTS rate")
    ax.set_xticks(np.arange(len(names)), [METHOD_LABELS[name] for name in names])
    ax.set(ylabel="Click rate (%)", title="BTS policy: OPE estimate versus observed clicks")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "ope_benchmark.png", dpi=160)
    plt.close(fig)

    metrics = report["ranking_metrics"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    labels = ["Popularity", "Two-stage"]
    for ax, key, title in [
        (axes[0], "recall_at_10", "Candidate Recall@10"),
        (axes[1], "ndcg_at_3", "Logged-click nDCG@3"),
    ]:
        values = [metrics["popularity_only"][key], metrics["two_stage"][key]]
        ax.bar(labels, values, color=["#888888", "#2765aa"])
        ax.set_ylim(0, min(1.0, max(values) * 1.25 + 0.01))
        ax.set_title(title)
        ax.set_ylabel("Position-standardized score")
    fig.tight_layout()
    fig.savefig(RESULTS / "ranking_metrics.png", dpi=160)
    plt.close(fig)


def observed_random_rate(position: np.ndarray, reward: np.ndarray) -> dict[str, Any]:
    """Standardize factual Random clicks across the three display slots."""
    counts = np.array([np.sum(position == pos) for pos in range(N_POSITIONS)])
    clicks = np.array([np.sum(reward[position == pos]) for pos in range(N_POSITIONS)])
    rates = clicks / counts
    value = float(rates.mean())
    variance = float(np.sum(rates * (1 - rates) / counts) / (N_POSITIONS**2))
    margin = 1.96 * np.sqrt(variance)
    return {
        "rows": int(counts.sum()), "clicks": int(clicks.sum()),
        "position_rates": rates.tolist(),
        "standardized_rate": value,
        "normal_95_ci": [max(0.0, float(value - margin)), float(value + margin)],
    }


def main() -> None:
    """Train without evaluation leakage and save all verified measurements."""
    for member in MEMBERS:
        if not verify_local(member):
            raise ValueError(f"Missing or corrupted input: {member.relative_path}")
    dataset, train, evaluation = load_dataset()
    total = dataset.n_rounds
    train_end = int(train["n_rounds"])
    fit_end = int(total * FIT_FRACTION)
    if train_end != int(total * TRAIN_FRACTION):
        raise AssertionError("Unexpected chronological split")
    threshold = str(dataset.data["timestamp"].iloc[train_end])
    print(f"Random rows: {total}; fit: {fit_end}; calibration: {train_end-fit_end}; OPE: {total-train_end}", flush=True)
    store = encode_features(dataset, fit_end)
    full_feedback = dataset.obtain_batch_bandit_feedback()
    aware = fit_calibrated_model(store, full_feedback, fit_end, train_end, True)
    blind = fit_calibrated_model(store, full_feedback, fit_end, train_end, False)
    diagnostics = model_diagnostics(aware, blind, store, evaluation, train_end)
    print(f"Reward model diagnostics: {diagnostics}", flush=True)
    q_hat = score_all_actions(aware, store, train_end, total, dataset.n_actions)
    print("Scored all evaluation item-position pairs", flush=True)

    hybrid_scores, popularity_scores, candidate_diagnostics = candidate_scores(
        store, np.asarray(train["action"]), np.asarray(train["reward"]), train_end
    )
    hybrid_candidates, popular_candidates = top_candidates(
        hybrid_scores, popularity_scores
    )
    ranked = rerank(hybrid_candidates, q_hat)
    popular_ranked = popular_candidates[:, :TOP_RANKED]
    action = np.asarray(evaluation["action"])
    position = np.asarray(evaluation["position"])
    reward = np.asarray(evaluation["reward"])
    ranking_metrics = {
        "popularity_only": logged_ranking_metrics(
            action, position, reward, popular_candidates, popular_ranked
        ),
        "two_stage": logged_ranking_metrics(
            action, position, reward, hybrid_candidates, ranked
        ),
    }

    reference_policy = BernoulliTS(
        n_actions=dataset.n_actions, len_list=N_POSITIONS,
        is_zozotown_prior=True, campaign=CAMPAIGN, random_state=37,
    )
    prior_distribution = reference_policy.compute_batch_action_dist(
        n_sim=BTS_SIMULATIONS, n_rounds=1
    )[0].astype(np.float32)
    bts_dist, observed, bts_reconstruction = reconstruct_bts_policy(
        threshold, dataset.data["timestamp"].iloc[train_end:],
        dataset.n_actions, prior_distribution,
    )
    new_dist = epsilon_slate_policy(ranked, dataset.n_actions)
    print(f"Observed BTS matched-window rate: {observed['standardized_rate']}", flush=True)
    bts_benchmark = estimate_policy(evaluation, bts_dist, q_hat)
    prior_dist = np.broadcast_to(prior_distribution, bts_dist.shape)
    prior_benchmark = estimate_policy(evaluation, prior_dist, q_hat)
    new_policy_ope = estimate_policy(evaluation, new_dist, q_hat)

    report: dict[str, Any] = {
        "source": "ZOZO Research Open Bandit Dataset, Men campaign",
        "split": {
            "random_total": total, "fit_rows": fit_end,
            "calibration_rows": train_end - fit_end,
            "evaluation_rows": total - train_end,
            "evaluation_clicks": int(reward.sum()),
            "evaluation_start_timestamp": threshold,
        },
        "position_click_rates_random_eval": [
            float(reward[position == pos].mean()) for pos in range(N_POSITIONS)
        ],
        "model": diagnostics,
        "candidate_generation": candidate_diagnostics,
        "ranking_metrics": ranking_metrics,
        "observed_random": observed_random_rate(position, reward),
        "observed_bts": observed,
        "bts_policy_reconstruction": bts_reconstruction,
        "bts_benchmark": bts_benchmark,
        "fixed_prior_diagnostic": prior_benchmark,
        "new_policy_ope": new_policy_ope,
        "policy": {
            "candidate_count": TOP_CANDIDATES,
            "ranked_count": TOP_RANKED,
            "uniform_slate_exploration": EXPLORATION,
            "bts_monte_carlo_simulations": BTS_SIMULATIONS,
        },
    }
    save_tables(report)
    save_plots(report)
    print("Experiment complete", flush=True)


if __name__ == "__main__":
    main()
