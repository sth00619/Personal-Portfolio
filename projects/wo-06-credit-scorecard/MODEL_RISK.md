# WO-06 Model Risk Register

This is a retrospective portfolio demonstration, not a production credit approval model. No applicant was actually declined by this code.

| Risk | Evidence / mitigation | Remaining limitation |
|---|---|---|
| Feature leakage | `src/data.py` accepts only five application-time variables: revenue, dti_n, loan_amnt, fico_n, experience_c. Target, origination date, loan status, interest rate, grade, recoveries, and payment amounts cannot enter either model. The allowlist is tested. | The data curators' feature provenance is accepted as documented; independent source-system audit is unavailable. |
| Time leakage | Every validation origination month follows all training origination months. Binning, IV selection, logistic fit, and LightGBM fit occur inside each expanding fold. Optuna uses only the final month inside the first training window. | **Outcome-observation dates are absent.** A loan's final status might not have been known when the next month's model would be fitted. This is retrospective vintage validation, not a verified production walk-forward backtest. |
| Survivorship and censoring | Data curators include only final-status loans and exclude open/transitory loans. | More recent vintages may be selected toward quickly resolved loans. Monthly Gini changes could reflect label selection as well as model drift. |
| Acceptance bias | Both models learn from originated loans. | Rejected applicants have no observed loan outcome. Reported AUC/Gini do not estimate performance on the full applicant pool. |
| Calibration | Both models output probabilities and the scorecard applies an explicit PDO scale. | ROC AUC/Gini do not establish calibrated PD. A production use case needs calibration plots, Brier score, and validation on a clearly defined performance horizon. |
| Stability | PSI compares each fold's training score distribution with the next origination month, using training-derived quantile edges. `PSI ≥ 0.10` prompts investigation and `PSI > 0.25` triggers retraining review. | Thresholds are operational heuristics, not regulatory rules. PSI alone cannot diagnose the source of drift or mandate automatic deployment. |
| Explainability | WoE bins and logistic coefficients are additive. A high-PD example includes positive raw-log-odds Tree SHAP contributors. | SHAP contributions are model explanations, not validated legal adverse-action notices or causal reasons. A separate policy, fair-lending, and customer-communication review is required. |
| Fairness and privacy | Identifier, state, ZIP code, free text, and occupation are excluded from model features and published example. | Protected-class labels are unavailable, so disparate impact and subgroup calibration are unmeasured. Income, FICO, and experience may still proxy protected attributes. |
| Reproducibility | Zenodo record and checksum are pinned; sampling seed, library versions, Docker image, and experiment configuration are recorded. Raw data is ignored by Git. | Upstream availability and platform-specific solver behavior can affect a rerun. |

## Monitoring decision

The PSI signal is an **investigation/retraining-review queue**, not an automatic retrain or a credit decision. An analyst should first verify data pipelines, sample mix, outcome maturity, segment-level performance, calibration, and fair-lending impact. A new model needs independently reviewed validation before deployment.
