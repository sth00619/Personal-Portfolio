"""Run retrospective monthly credit risk comparisons and export evidence."""

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
import shap

from src.data import FEATURES, TARGET, expanding_month_splits, load_applications
from src.metrics import auc_gini, population_stability_index, psi_signal
from src.models import (
    BASE_GOOD_BAD_ODDS,
    BASE_SCORE,
    POINTS_TO_DOUBLE_ODDS,
    Scorecard,
    fit_challenger,
    fit_scorecard,
)

START_MONTH = "2015-01"
END_MONTH = "2017-06"
MONTHLY_CAP = 1500
VALIDATION_MONTHS = 6
MIN_TRAIN_MONTHS = 12
OPTUNA_TRIALS = 4
RANDOM_STATE = 42
PLOT_DPI = 160
FIGURE_SIZE = (9, 4.5)


def tune_challenger(
    train: pd.DataFrame, feature_names: tuple[str, ...]
) -> tuple[dict[str, int | float], list[dict[str, Any]]]:
    """Tune on the final training month without inspecting OOT months."""
    months = sorted(train["month"].unique().tolist())
    tuning_month = months[-1]
    fit_rows = train[train["month"] < tuning_month]
    validation = train[train["month"] == tuning_month]
    if fit_rows[TARGET].nunique() != 2 or validation[TARGET].nunique() != 2:
        raise ValueError("Internal tuning split lacks both outcome classes")

    def objective(trial: optuna.Trial) -> float:
        """Optimize AUC on the last month available before the first OOT fold."""
        parameters = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 250),
            "num_leaves": trial.suggest_int("num_leaves", 7, 31),
            "min_child_samples": trial.suggest_int("min_child_samples", 50, 180),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.12),
        }
        model = fit_challenger(fit_rows[list(feature_names)], fit_rows[TARGET].to_numpy(), parameters)
        prediction = model.predict_proba(validation[list(feature_names)])[:, 1]
        return auc_gini(validation[TARGET].to_numpy(), prediction)[0]

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(objective, n_trials=OPTUNA_TRIALS)
    trials = [
        {"number": trial.number, "auc": float(trial.value), "parameters": trial.params}
        for trial in study.trials
    ]
    return study.best_params, trials


def shap_reasons(model: Any, applicant: pd.DataFrame) -> dict[str, Any]:
    """Return risk-raising SHAP contributions for a hypothetical decline."""
    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(applicant)
    if isinstance(values, list):
        values = values[1]
    contributions = np.asarray(values)
    if contributions.ndim == 3:
        contributions = contributions[:, :, 1]
    signed = contributions[0]
    factors = [
        {
            "feature": feature,
            "value": float(applicant.iloc[0][feature]) if pd.notna(applicant.iloc[0][feature]) else None,
            "shap_log_odds": float(contribution),
        }
        for feature, contribution in zip(applicant.columns, signed)
        if contribution > 0
    ]
    factors.sort(key=lambda item: item["shap_log_odds"], reverse=True)
    return {"positive_risk_contributors": factors[:3], "shap_unit": "raw log-odds"}


def plot_monthly_results(rows: list[dict[str, Any]], output: Path) -> None:
    """Save measured monthly Gini and PSI trends as a shareable figure."""
    months = [row["month"] for row in rows]
    score_gini = [row["scorecard"]["gini"] for row in rows]
    challenger_gini = [row["lightgbm"]["gini"] for row in rows]
    score_psi = [row["scorecard"]["psi"] for row in rows]
    challenger_psi = [row["lightgbm"]["psi"] for row in rows]
    figure, axes = plt.subplots(2, 1, figsize=FIGURE_SIZE, sharex=True)
    axes[0].plot(months, score_gini, marker="o", label="WoE scorecard")
    axes[0].plot(months, challenger_gini, marker="o", label="LightGBM")
    axes[0].set_ylabel("Gini = 2 × AUC − 1")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    axes[1].plot(months, score_psi, marker="o", label="WoE scorecard")
    axes[1].plot(months, challenger_psi, marker="o", label="LightGBM")
    axes[1].axhline(0.10, color="orange", linestyle="--", label="investigate 0.10")
    axes[1].axhline(0.25, color="red", linestyle="--", label="retrain review >0.25")
    axes[1].set_ylabel("PSI vs fold training")
    axes[1].grid(alpha=0.25)
    axes[1].legend(ncol=2, fontsize=8)
    axes[1].tick_params(axis="x", rotation=30)
    figure.tight_layout()
    figure.savefig(output, dpi=PLOT_DPI)
    plt.close(figure)


def write_scorecard_points(scorecard: Scorecard, results_dir: Path) -> None:
    """Export the final fold's WoE bins and additive point contributions."""
    factor = POINTS_TO_DOUBLE_ODDS / np.log(2)
    offset = BASE_SCORE - factor * np.log(BASE_GOOD_BAD_ODDS)
    intercept_points = float(offset - factor * scorecard.model.intercept_[0])
    rows = []
    for feature, coefficient in zip(scorecard.selected_features, scorecard.model.coef_[0]):
        table = scorecard.binners[feature].binning_table.build()
        for _, bin_row in table.iterrows():
            if str(bin_row["Bin"]) == "Totals":
                continue
            parsed_woe = pd.to_numeric(bin_row["WoE"], errors="coerce")
            if int(bin_row["Count"]) == 0 or pd.isna(parsed_woe):
                continue
            woe = float(parsed_woe)
            rows.append(
                {
                    "feature": feature,
                    "bin": str(bin_row["Bin"]),
                    "count": int(bin_row["Count"]),
                    "event_rate": float(bin_row["Event rate"]),
                    "woe": woe,
                    "iv": float(bin_row["IV"]),
                    "logistic_coefficient": float(coefficient),
                    "point_contribution": float(-factor * coefficient * woe),
                }
            )
    pd.DataFrame(rows).to_csv(results_dir / "scorecard_bins.csv", index=False)
    scaling = {
        "base_score": BASE_SCORE,
        "base_good_bad_odds": BASE_GOOD_BAD_ODDS,
        "points_to_double_odds": POINTS_TO_DOUBLE_ODDS,
        "intercept_points": intercept_points,
        "formula": "score = intercept_points + sum(point_contribution for selected bins)",
    }
    (results_dir / "scorecard_scaling.json").write_text(json.dumps(scaling, indent=2), encoding="utf-8")


def _model_summary(rows: list[dict[str, Any]], name: str) -> dict[str, float]:
    """Aggregate equal-weight monthly discrimination and score drift."""
    return {
        "mean_auc": float(np.mean([row[name]["auc"] for row in rows])),
        "mean_gini": float(np.mean([row[name]["gini"] for row in rows])),
        "gini_std": float(np.std([row[name]["gini"] for row in rows], ddof=0)),
        "mean_psi": float(np.mean([row[name]["psi"] for row in rows])),
        "max_psi": float(np.max([row[name]["psi"] for row in rows])),
    }


def run_experiment(
    data_path: Path,
    results_dir: Path,
    start_month: str = START_MONTH,
    end_month: str = END_MONTH,
    monthly_cap: int = MONTHLY_CAP,
) -> dict[str, Any]:
    """Execute all expanding folds, save metrics, reasons, and stability plot."""
    results_dir.mkdir(parents=True, exist_ok=True)
    frame = load_applications(data_path, start_month, end_month, monthly_cap)
    folds = expanding_month_splits(frame, VALIDATION_MONTHS, MIN_TRAIN_MONTHS)
    initial_train = folds[0][1]
    internal_validation_month = initial_train["month"].max()
    pre_tuning_rows = initial_train[initial_train["month"] < internal_validation_month]
    initial_scorecard = fit_scorecard(
        pre_tuning_rows[list(FEATURES)], pre_tuning_rows[TARGET].to_numpy(dtype=int)
    )
    challenger_parameters, tuning_trials = tune_challenger(initial_train, initial_scorecard.selected_features)
    rows: list[dict[str, Any]] = []
    last_model: Any = None
    last_validation: pd.DataFrame | None = None
    last_predictions: np.ndarray | None = None
    last_iv: dict[str, float] = {}
    last_features: tuple[str, ...] = ()
    last_scorecard: Scorecard | None = None
    for month, train, validation in folds:
        train_x = train[list(FEATURES)]
        validation_x = validation[list(FEATURES)]
        train_y = train[TARGET].to_numpy(dtype=int)
        validation_y = validation[TARGET].to_numpy(dtype=int)
        scorecard = fit_scorecard(train_x, train_y)
        challenger_x = train_x[list(scorecard.selected_features)]
        challenger_validation_x = validation_x[list(scorecard.selected_features)]
        challenger = fit_challenger(challenger_x, train_y, challenger_parameters)
        score_train = scorecard.predict_pd(train_x)
        score_test = scorecard.predict_pd(validation_x)
        light_train = challenger.predict_proba(challenger_x)[:, 1]
        light_test = challenger.predict_proba(challenger_validation_x)[:, 1]
        score_auc, score_gini = auc_gini(validation_y, score_test)
        light_auc, light_gini = auc_gini(validation_y, light_test)
        score_psi = population_stability_index(score_train, score_test)
        light_psi = population_stability_index(light_train, light_test)
        rows.append(
            {
                "month": month,
                "train_end_month": train["month"].max(),
                "train_count": len(train),
                "validation_count": len(validation),
                "default_rate": float(validation_y.mean()),
                "selected_features": list(scorecard.selected_features),
                "scorecard": {"auc": score_auc, "gini": score_gini, "psi": score_psi, "signal": psi_signal(score_psi)},
                "lightgbm": {"auc": light_auc, "gini": light_gini, "psi": light_psi, "signal": psi_signal(light_psi)},
            }
        )
        last_model = challenger
        last_validation = challenger_validation_x
        last_predictions = light_test
        last_iv = scorecard.information_value
        last_features = scorecard.selected_features
        last_scorecard = scorecard
        print(f"{month}: scorecard Gini={score_gini:.3f}, LightGBM Gini={light_gini:.3f}, PSI={score_psi:.3f}/{light_psi:.3f}", flush=True)
    assert last_model is not None and last_validation is not None and last_predictions is not None
    assert last_scorecard is not None
    write_scorecard_points(last_scorecard, results_dir)
    highest_risk_position = int(np.argmax(last_predictions))
    applicant = last_validation.iloc[[highest_risk_position]]
    example = {
        "month": rows[-1]["month"],
        "selection": "highest estimated PD in final OOT month",
        "hypothetical_decision": "manual_review",
        "estimated_pd": float(last_predictions[highest_risk_position]),
        **shap_reasons(last_model, applicant),
    }
    comparison = {
        "scorecard": {**_model_summary(rows, "scorecard"), "explainability": "additive WoE bins and PDO score"},
        "lightgbm": {**_model_summary(rows, "lightgbm"), "explainability": "post-hoc Tree SHAP; local attribution, not causal"},
    }
    output = {
        "dataset": "Zenodo 11295916 Lending Club granting model",
        "data_range": [start_month, end_month],
        "sampled_rows": len(frame),
        "monthly_cap": monthly_cap,
        "validation_scheme": "retrospective expanding monthly originations; no random split",
        "label_availability_verified": False,
        "feature_allowlist": list(FEATURES),
        "tuning_validation_month": sorted(folds[0][1]["month"].unique().tolist())[-1],
        "optuna_trials": tuning_trials,
        "selected_lightgbm_parameters": challenger_parameters,
        "final_fold_information_value": last_iv,
        "final_fold_selected_scorecard_features": list(last_features),
        "monthly": rows,
        "comparison": comparison,
        "example": example,
        "retrain_review_months": {
            name: [row["month"] for row in rows if row[name]["signal"] == "RETRAIN_REVIEW"]
            for name in ("scorecard", "lightgbm")
        },
    }
    (results_dir / "experiment.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_monthly_results(rows, results_dir / "stability.png")
    return output
