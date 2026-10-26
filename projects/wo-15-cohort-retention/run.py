"""Load Olist CSVs into PostgreSQL, run SQL analyses, and build portfolio outputs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from lifelines import KaplanMeierFitter
from scipy.stats import chi2_contingency, ttest_ind


PROJECT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_DIR / "results"
TABLES = {
    "cohort_retention": "SELECT * FROM analytics.cohort_retention ORDER BY cohort_month, cohort_age",
    "monthly_metric_tree": "SELECT * FROM analytics.monthly_metric_tree ORDER BY purchase_month",
    "rfm_profile": "SELECT * FROM analytics.rfm_profile ORDER BY customers DESC",
    "customer_id_effect": "SELECT * FROM analytics.customer_id_effect ORDER BY identifier",
    "first_order_experience": "SELECT * FROM analytics.first_order_experience ORDER BY customer_unique_id",
    "survival": "SELECT * FROM analytics.survival ORDER BY customer_unique_id",
    "category_repeat_profile": "SELECT * FROM analytics.category_repeat_profile ORDER BY repeat_rate DESC, customers DESC",
}
FIGURE_DPI = 160
MIN_MONTHLY_ORDERS = 500
SUSTAINED_MONTH_COUNT = 3
MIN_COHORT_CUSTOMERS = 100


def run_command(command: list[str], capture: bool = False) -> str:
    """Run a project command and surface useful process output on failure."""

    result = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else ""


def psql_file(filename: str) -> None:
    """Execute a SQL file inside the local compose PostgreSQL service."""

    run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "olist",
            "-d",
            "olist",
            "-f",
            f"/sql/{filename}",
        ]
    )


def export_table(name: str, query: str) -> pd.DataFrame:
    """Export one SQL result through psql COPY and persist its CSV evidence."""

    copy_query = f"\\copy ({query}) TO STDOUT WITH (FORMAT csv, HEADER true)"
    csv_text = run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "olist",
            "-d",
            "olist",
            "-c",
            copy_query,
        ],
        capture=True,
    )
    destination = RESULTS_DIR / f"{name}.csv"
    destination.write_text(csv_text, encoding="utf-8")
    return pd.read_csv(destination)


def plot_cohort_retention(frame: pd.DataFrame) -> None:
    """Render a monthly retention heatmap with ordinal cohort labels."""

    sizes = frame.groupby("cohort_month")["cohort_customers"].first()
    shown_months = sizes.loc[sizes.ge(MIN_COHORT_CUSTOMERS)].index
    frame = frame.loc[frame["cohort_month"].isin(shown_months)]
    pivot = frame.pivot(index="cohort_month", columns="cohort_age", values="retention_rate")
    cohort_months = pivot.index.tolist()
    labels = {month: f"C{index + 1:02d}" for index, month in enumerate(cohort_months)}
    pivot.index = [labels[month] for month in cohort_months]
    figure_height = max(5.0, min(12.0, 0.32 * len(pivot)))
    figure, axis = plt.subplots(figsize=(12.0, figure_height))
    sns.heatmap(
        pivot,
        cmap="YlGnBu",
        vmin=0,
        vmax=1,
        mask=pivot.isna(),
        linewidths=0.15,
        cbar_kws={"label": "Customer retention"},
        ax=axis,
    )
    axis.set_title(
        f"Delivered-order cohort retention (cohorts >= {MIN_COHORT_CUSTOMERS} customers)"
    )
    axis.set_xlabel("Months since first delivered order")
    axis.set_ylabel("First-order cohort (chronological ordinal)")
    figure.tight_layout()
    figure.savefig(RESULTS_DIR / "cohort_retention_heatmap.png", dpi=FIGURE_DPI)
    plt.close(figure)


def plot_metric_tree(frame: pd.DataFrame) -> None:
    """Show revenue and its exact multiplicative components as indexed series."""

    complete = eligible_complete_months(frame)
    series = {
        "Revenue": complete["revenue"],
        "Customers": complete["customers"],
        "Orders per customer": complete["orders_per_customer"],
        "Average order value": complete["average_order_value"],
    }
    figure, axis = plt.subplots(figsize=(10.0, 5.0))
    colors = ["#1d4ed8", "#059669", "#d97706", "#7c3aed"]
    for (label, values), color in zip(series.items(), colors, strict=True):
        index = values / values.iloc[0] * 100.0
        axis.plot(np.arange(len(index)), index, label=label, color=color, linewidth=1.8)
    axis.set_xlabel("Complete month sequence")
    axis.set_ylabel("Index (first complete month = 100)")
    axis.set_title("Revenue metric tree: buyers × frequency × average order value")
    axis.legend(frameon=False, ncol=2)
    axis.grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(RESULTS_DIR / "revenue_metric_tree.png", dpi=FIGURE_DPI)
    plt.close(figure)


def plot_rfm(frame: pd.DataFrame) -> None:
    """Plot customer counts for the most populated evidence-backed RFM cells."""

    shown = frame.nlargest(15, "customers").sort_values("customers").copy()
    shown["rfm_segment"] = shown["rfm_segment"].astype(str)
    figure, axis = plt.subplots(figsize=(9.0, 5.5))
    axis.barh(shown["rfm_segment"], shown["customers"], color="#2563eb")
    axis.set_xlabel("Customers")
    axis.set_ylabel("RFM score (R-F-M)")
    axis.set_title("Largest RFM segments")
    figure.tight_layout()
    figure.savefig(RESULTS_DIR / "rfm_segments.png", dpi=FIGURE_DPI)
    plt.close(figure)


def plot_survival(frame: pd.DataFrame) -> dict[str, float | int]:
    """Fit and plot Kaplan-Meier time to second purchase with right censoring."""

    durations = frame["duration_days"].to_numpy(dtype=float)
    events = as_boolean(frame["repurchased"]).to_numpy(dtype=bool)
    fitter = KaplanMeierFitter(label="No second delivered purchase")
    fitter.fit(durations, event_observed=events)
    axis = fitter.plot_survival_function(ci_show=True, color="#2563eb")
    axis.set_title("Kaplan-Meier curve: time to second delivered purchase")
    axis.set_xlabel("Days since first delivered order")
    axis.set_ylabel("Probability of no second delivered purchase")
    axis.set_ylim(0, 1.02)
    axis.grid(alpha=0.2)
    axis.figure.tight_layout()
    axis.figure.savefig(RESULTS_DIR / "repurchase_kaplan_meier.png", dpi=FIGURE_DPI)
    plt.close(axis.figure)
    median = fitter.median_survival_time_
    return {
        "customers": int(len(frame)),
        "repeat_events": int(events.sum()),
        "censored_customers": int((~events).sum()),
        "median_days_without_second_purchase": (
            float(median) if np.isfinite(median) else None
        ),
        "survival_at_90_days": float(fitter.predict(90)),
        "survival_at_180_days": float(fitter.predict(180)),
    }


def experience_statistics(frame: pd.DataFrame) -> dict[str, object]:
    """Compare first-order reviews and delays between one-time and repeat groups."""

    frame = frame.copy()
    for column in ("repurchased", "delivery_delayed"):
        frame[column] = as_boolean(frame[column])
    review = frame.dropna(subset=["review_score"])
    one_time_score = review.loc[~review["repurchased"], "review_score"].astype(float)
    repeat_score = review.loc[review["repurchased"], "review_score"].astype(float)
    review_test = ttest_ind(one_time_score, repeat_score, equal_var=False)

    delay_frame = frame.dropna(subset=["delivery_delayed"])
    contingency = pd.crosstab(delay_frame["repurchased"], delay_frame["delivery_delayed"])
    chi_square, p_value, degrees, _ = chi2_contingency(contingency)
    one_time_delay = delay_frame.loc[~delay_frame["repurchased"], "delivery_delayed"].mean()
    repeat_delay = delay_frame.loc[delay_frame["repurchased"], "delivery_delayed"].mean()
    return {
        "review": {
            "one_time_n": int(len(one_time_score)),
            "repeat_n": int(len(repeat_score)),
            "one_time_mean": float(one_time_score.mean()),
            "repeat_mean": float(repeat_score.mean()),
            "difference_repeat_minus_one_time": float(repeat_score.mean() - one_time_score.mean()),
            "welch_t_statistic": float(review_test.statistic),
            "p_value": float(review_test.pvalue),
        },
        "delivery_delay": {
            "one_time_n": int((~delay_frame["repurchased"]).sum()),
            "repeat_n": int(delay_frame["repurchased"].sum()),
            "one_time_rate": float(one_time_delay),
            "repeat_rate": float(repeat_delay),
            "difference_repeat_minus_one_time": float(repeat_delay - one_time_delay),
            "chi_square": float(chi_square),
            "degrees_of_freedom": int(degrees),
            "p_value": float(p_value),
            "contingency": contingency.to_dict(),
        },
    }


def as_boolean(values: pd.Series) -> pd.Series:
    """Convert PostgreSQL CSV boolean spellings to nullable Python booleans."""

    if values.dtype == bool:
        return values
    normalized = values.astype("string").str.lower()
    return normalized.map({"t": True, "f": False, "true": True, "false": False})


def eligible_complete_months(frame: pd.DataFrame) -> pd.DataFrame:
    """Select contiguous full months after three consecutive active months."""

    monthly = frame.sort_values("purchase_month").copy()
    latest_month = pd.to_datetime(monthly["purchase_month"]).max()
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"])
    monthly = monthly.loc[monthly["purchase_month"].lt(latest_month)].reset_index(drop=True)
    active = monthly["delivered_orders"].ge(MIN_MONTHLY_ORDERS).to_numpy()
    start = None
    for index in range(0, len(monthly) - SUSTAINED_MONTH_COUNT + 1):
        window = monthly.iloc[index : index + SUSTAINED_MONTH_COUNT]
        # Use calendar month numbers so February and 30-day months count correctly.
        month_numbers = window["purchase_month"].dt.year * 12 + window["purchase_month"].dt.month
        if active[index : index + SUSTAINED_MONTH_COUNT].all() and month_numbers.diff().dropna().eq(1).all():
            start = index
            break
    if start is None:
        raise ValueError("No sustained run of complete active months was found")
    eligible = monthly.iloc[start:].copy()
    month_numbers = eligible["purchase_month"].dt.year * 12 + eligible["purchase_month"].dt.month
    if not month_numbers.diff().dropna().eq(1).all():
        raise ValueError("Revenue decomposition requires contiguous calendar months")
    return eligible.reset_index(drop=True)


def build_revenue_decomposition(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate exact log-change contributions for the largest complete-month decline."""

    monthly = eligible_complete_months(frame)
    components = ["customers", "orders_per_customer", "average_order_value"]
    for column in ["revenue", *components]:
        monthly[f"previous_{column}"] = monthly[column].shift(1)
    monthly["revenue_change_rate"] = monthly["revenue"] / monthly["previous_revenue"] - 1
    monthly = monthly.dropna(subset=["previous_revenue"])
    for column in components:
        monthly[f"{column}_log_contribution"] = np.log(
            monthly[column] / monthly[f"previous_{column}"]
        )
    monthly["revenue_log_change"] = np.log(monthly["revenue"] / monthly["previous_revenue"])
    monthly["contribution_sum"] = monthly[
        [f"{column}_log_contribution" for column in components]
    ].sum(axis=1)
    if not np.allclose(monthly["contribution_sum"], monthly["revenue_log_change"]):
        raise ArithmeticError("Revenue metric-tree contributions do not reconcile")
    return monthly


def write_decision_memo(
    id_effect: pd.DataFrame,
    rfm: pd.DataFrame,
    survival: dict[str, float | int],
    experience: dict[str, object],
    decomposition: pd.DataFrame,
    category_profile: pd.DataFrame,
) -> dict[str, object]:
    """Write a concise bilingual decision memo from measured evidence."""

    unique_row = id_effect.loc[
        id_effect["population"].eq("delivered_orders")
        & id_effect["identifier"].eq("customer_unique_id")
    ].iloc[0]
    wrong_row = id_effect.loc[
        id_effect["population"].eq("delivered_orders")
        & id_effect["identifier"].eq("customer_id")
    ].iloc[0]
    all_order_unique = id_effect.loc[
        id_effect["population"].eq("all_orders")
        & id_effect["identifier"].eq("customer_unique_id")
    ].iloc[0]
    all_order_wrong = id_effect.loc[
        id_effect["population"].eq("all_orders")
        & id_effect["identifier"].eq("customer_id")
    ].iloc[0]
    largest_decline = decomposition.loc[decomposition["revenue_change_rate"].idxmin()]
    largest_rfm = rfm.iloc[0]
    leading_category = category_profile.iloc[0]
    repeat_share = float(unique_row["repeat_rate"])
    review = experience["review"]
    delay = experience["delivery_delay"]
    memo = f"""# WO-15 Decision Memo | Cohort and Retention

## 의사결정 요약

**기존 고객 유지가 성장의 기본 레버라는 가정을 이 데이터만으로 채택하지 않는다.** 완료 주문 기준 고유 고객 재구매율은 {repeat_share:.2%}({int(unique_row['repeat_customers']):,}/{int(unique_row['customers']):,})다. RFM 빈도 점수는 대부분의 고객이 1회 구매인 분포를 보존하도록 1회 구매=1, 재구매=5의 두 단계로 구성했다. 반복 구매자를 위한 메시지·혜택 실험은 작고 검증 가능한 후보군에 한정하고, 단골 세그먼트 규모가 충분하다고 가정한 대규모 투자 근거로 사용하지 않는다.

## 근거

- 전체 주문을 `customer_id`로 세면 {int(all_order_wrong['customers']):,}개 주문 키에서 재구매가 0건이지만, `customer_unique_id`로 묶으면 {int(all_order_unique['customers']):,}명 중 {int(all_order_unique['repeat_customers']):,}명({float(all_order_unique['repeat_rate']):.2%})이 반복 주문했다. 주 분석의 완료 주문(배송 완료)은 {int(unique_row['customers']):,}명 중 {int(unique_row['repeat_customers']):,}명({repeat_share:.2%})이다.
- 가장 큰 RFM 셀은 `{largest_rfm['rfm_segment']}`이며 {int(largest_rfm['customers']):,}명, 평균 구매액 {float(largest_rfm['average_monetary']):,.2f}이다. 표의 금액 단위는 데이터의 결제 가치 단위를 따른다.
- Kaplan-Meier 추정에서 90일 내 두 번째 완료 주문이 관측되지 않은 생존 확률은 {float(survival['survival_at_90_days']):.2%}다. 중도절단 고객은 반복이 없었다고 단정하지 않는다.
- 첫 주문 리뷰 평균은 1회 구매 {float(review['one_time_mean']):.3f}, 재구매 {float(review['repeat_mean']):.3f}; Welch t-test p={float(review['p_value']):.3g} (반복군 n={int(review['repeat_n']):,}).
- 첫 주문 배송 지연 비율은 1회 구매 {float(delay['one_time_rate']):.2%}, 재구매 {float(delay['repeat_rate']):.2%}; 카이제곱 검정 p={float(delay['p_value']):.3g}.
- 첫 구매 상품군 가운데 최소 200명 기준 재구매율이 가장 높은 범주는 `{leading_category['category']}`({float(leading_category['repeat_rate']):.2%}, n={int(leading_category['customers']):,})다. 이는 선택 편향과 다중 비교를 보정하지 않은 관찰값이다.
- 완전한 월만 비교한 매출 최대 하락은 전월 대비 {float(largest_decline['revenue_change_rate']):.2%}. 로그 변화 기여는 고객 수 {float(largest_decline['customers_log_contribution']):+.4f}, 고객당 주문 수 {float(largest_decline['orders_per_customer_log_contribution']):+.4f}, 객단가 {float(largest_decline['average_order_value_log_contribution']):+.4f}이며 합계가 매출 로그 변화와 일치한다.

## 권고와 경계

다음 투자로는 재구매 가능성이 관측된 고객군의 소규모 유지 실험과 상품 카테고리별 첫 구매 후 재방문 분석을 제안한다. Olist 자료는 마켓플레이스의 관측 주문만 포함하며 비구매 고객, 채널 노출, 고객 유입 비용은 제공하지 않는다. 첫 관측 구매를 실제 최초 구매로 볼 수 없고 자료 종료 시점의 코호트는 추적 기간이 짧다. 리뷰·지연 차이는 상관관계이며 원인 효과가 아니다.

## English summary

The observed delivered-order repeat rate among `customer_unique_id` customers is {repeat_share:.2%}. The order-level `customer_id` would incorrectly imply a zero repeat rate. The cohort, RFM, survival, and first-order experience analyses support a narrowly scoped retention experiment, while the marketplace dataset does not establish causality or represent non-buyers.
"""
    (RESULTS_DIR / "decision_memo.md").write_text(memo, encoding="utf-8")
    return {
        "customer_id_effect": {
            "all_orders_customer_id_customers": int(all_order_wrong["customers"]),
            "all_orders_customer_unique_id_customers": int(all_order_unique["customers"]),
            "all_orders_repeat_customers": int(all_order_unique["repeat_customers"]),
            "all_orders_repeat_rate": float(all_order_unique["repeat_rate"]),
            "delivered_customer_id_repeat_rate": float(wrong_row["repeat_rate"]),
            "customer_unique_id_customers": int(unique_row["customers"]),
            "customer_unique_id_repeat_customers": int(unique_row["repeat_customers"]),
            "customer_unique_id_repeat_rate": repeat_share,
        },
        "largest_revenue_decline": {
            "purchase_month": str(largest_decline["purchase_month"]),
            "change_rate": float(largest_decline["revenue_change_rate"]),
            "customer_count_log_contribution": float(largest_decline["customers_log_contribution"]),
            "frequency_log_contribution": float(largest_decline["orders_per_customer_log_contribution"]),
            "aov_log_contribution": float(largest_decline["average_order_value_log_contribution"]),
        },
        "survival": survival,
        "experience": experience,
        "highest_repeat_category": {
            "category": str(leading_category["category"]),
            "customers": int(leading_category["customers"]),
            "repeat_rate": float(leading_category["repeat_rate"]),
        },
        "rfm_segments": int(len(rfm)),
    }


def run_analysis(load_raw: bool) -> dict[str, object]:
    """Run PostgreSQL transformations, export evidence, and build plots and memo."""

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_command(
        ["docker", "compose", "up", "-d", "--wait", "db"]
    )
    if load_raw:
        psql_file("01_load.sql")
        psql_file("02_analysis.sql")

    exported = {name: export_table(name, query) for name, query in TABLES.items()}
    cohort = exported["cohort_retention"]
    metrics = exported["monthly_metric_tree"]
    rfm = exported["rfm_profile"]
    id_effect = exported["customer_id_effect"]
    experience_frame = exported["first_order_experience"]
    survival_frame = exported["survival"]

    plot_cohort_retention(cohort)
    plot_metric_tree(metrics)
    plot_rfm(rfm)
    survival_summary = plot_survival(survival_frame)
    experience_summary = experience_statistics(experience_frame)
    decomposition = build_revenue_decomposition(metrics)
    decomposition.to_csv(RESULTS_DIR / "revenue_decline_decomposition.csv", index=False)
    summary = write_decision_memo(
        id_effect,
        rfm,
        survival_summary,
        experience_summary,
        decomposition,
        exported["category_repeat_profile"],
    )
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    """Start PostgreSQL and create the complete project evidence package."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="reuse analytical tables already present in the local compose database",
    )
    args = parser.parse_args()
    summary = run_analysis(load_raw=not args.skip_load)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

