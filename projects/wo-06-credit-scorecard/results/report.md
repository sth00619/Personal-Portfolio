# WO-06 measured results

Source: [Zenodo Lending Club granting model, DOI 10.5281/zenodo.11295916](https://zenodo.org/records/11295916), CC BY 4.0. Exact run: Python 3.11 Docker image, 2015-01 to 2017-06, 1,500 randomly sampled records per origination month with seed 42; 45,000 rows in 30 months. The last six months are single-month, expanding-window validation folds. Tuning used 2016-12 only inside the initial training window. The JSON in this directory is the machine-readable source for every rounded number below.

| Month | OOT loans | Default rate | Scorecard AUC | Scorecard Gini | Scorecard PSI | LightGBM AUC | LightGBM Gini | LightGBM PSI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017-01 | 1,500 | 0.217 | 0.653 | 0.306 | 0.017 | 0.645 | 0.290 | 0.019 |
| 2017-02 | 1,500 | 0.225 | 0.647 | 0.294 | 0.030 | 0.652 | 0.305 | 0.027 |
| 2017-03 | 1,500 | 0.227 | 0.659 | 0.318 | 0.027 | 0.660 | 0.320 | 0.025 |
| 2017-04 | 1,500 | 0.234 | 0.665 | 0.331 | 0.026 | 0.671 | 0.342 | 0.029 |
| 2017-05 | 1,500 | 0.245 | 0.642 | 0.285 | 0.024 | 0.634 | 0.267 | 0.025 |
| 2017-06 | 1,500 | 0.236 | 0.647 | 0.293 | 0.035 | 0.655 | 0.310 | 0.029 |

![Monthly Gini and PSI](stability.png)

| Axis | WoE logistic scorecard | LightGBM challenger |
|---|---|---|
| Discrimination | Mean AUC 0.6522; mean Gini **0.3045** | Mean AUC 0.6527; mean Gini **0.3055** |
| Explainability | IV-selected, fixed WoE bins and additive logistic coefficients; transparent PDO points | Tree SHAP provides local, post-hoc risk contributions; less directly auditable |
| Stability | Monthly Gini population SD **0.0158**; mean PSI **0.0265**, maximum **0.0349** | Monthly Gini population SD **0.0233**; mean PSI **0.0256**, maximum **0.0295** |

The mean Gini difference is only 0.0010. No uncertainty interval was estimated, so this is not evidence of superior predictive performance. The scorecard has lower observed month-to-month Gini variation; LightGBM has a slightly lower mean and maximum PSI. Both models remain below the 0.10 investigation threshold for this sample. PSI is computed against **each fold's training score distribution**, so values are for local one-month checks rather than drift versus one permanently frozen production model.

## IV, tuning, and applicant example

Final-fold IV: fico_n **0.1264**, dti_n **0.0736**, revenue **0.0336**, loan_amnt **0.0331**, experience_c **0.0000**. Training-only IV threshold 0.01 excluded experience_c. **Both models used the same four selected variables in every OOT fold.** Four Optuna trials on the 2016-12 internal validation month produced a best AUC of **0.6453** with 123 trees, 10 leaves, minimum 57 child samples, and learning rate 0.1080. This small search is an attempt record, not an extensive optimization claim.

The final fold's auditable [WoE bin and point-contribution table](scorecard_bins.csv) and [PDO scaling metadata](scorecard_scaling.json) are included. The score is **474.99 intercept points + the selected bin contributions**; 600 points correspond to good/bad odds 20 and doubling those odds adds 50 points. These are model scores, not validated lending cutoffs.

For the highest estimated-risk loan in 2017-06, LightGBM estimated PD **0.5404**. This is a **hypothetical manual-review example**, not an actual decline. Positive Tree SHAP contributions to default log-odds were dti_n **+0.682** (value 61.28), loan_amnt **+0.462** (30,000), and fico_n **+0.390** (667). The magnitudes are model contributions, not causal effects or legally approved adverse-action reasons.

## PSI alarm rule

- PSI < 0.10: stable monitoring band.
- 0.10 ≤ PSI ≤ 0.25: investigate sample mix and data pipeline.
- PSI > 0.25: create a retraining **review** signal, subject to outcome, calibration, and fairness validation before deployment.

The observed six-month run triggered **zero** retraining-review months for both models. The tested synthetic shifted distribution exceeded 0.25 and triggered `RETRAIN_REVIEW`.

## Interpretation boundary

The dataset has origination month but **no outcome-observation date**. All labels are final statuses known only in hindsight. Expanding splits prevent future **applications/features** from entering a past fit, but cannot prove that all training labels were available at that historical month. The data includes only funded, final-status loans, so acceptance and censoring biases remain. See [MODEL_RISK.md](../MODEL_RISK.md).
