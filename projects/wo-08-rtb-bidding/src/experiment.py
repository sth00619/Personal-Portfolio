"""Leakage-aware iPinYou CTR modeling and supported auction replay."""

from __future__ import annotations

import bz2
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from data.download import FILES, digest_file


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"
TRAIN_DAYS = ("20130606", "20130607")
CAL_DAY = "20130608"
TEST_DAY = "20130609"
ADVERTISER = "1458"
PRICE_SCALE = 1000.0
BUDGET_FRACTION = 0.5
HOURS = 24
PACING_GAIN = 1.25
PACING_MIN = 0.05
PACING_MAX = 3.0
FEATURE_COLUMNS = (
    "advertiser", "exchange", "region", "city", "domain", "slot_id",
    "slot_width", "slot_height", "slot_visibility", "slot_format", "creative", "hour",
)
CAT_COLUMNS = FEATURE_COLUMNS


@dataclass(frozen=True)
class Auction:
    """One observed impression eligible for supported bid reduction."""

    timestamp: str
    price: int
    logged_bid: int
    clicks: int
    pctr: float


@dataclass(frozen=True)
class Score:
    """Measured outcomes for one sequential policy replay."""

    strategy: str
    clicks: int
    clicked_impressions: int
    spend: float
    ecpc: float | None
    wins: int
    budget: float
    hourly_spend: list[float]


def click_counts(day: str) -> Counter[str]:
    """Count click events by bid ID; duplicates remain separate events."""
    counts: Counter[str] = Counter()
    with bz2.open(RAW / f"clk.{day}.txt.bz2", "rt") as handle:
        for line in handle:
            counts[line.split("\t", 1)[0]] += 1
    return counts


def impression_lines(day: str, prefix: bool) -> Iterator[str]:
    """Yield complete lines from a verified prefix or full BZip2 member."""
    filename = f"imp.{day}.prefix.bz2" if prefix else f"imp.{day}.txt.bz2"
    path = RAW / filename
    if prefix:
        decoder = bz2.BZ2Decompressor()
        decoded = decoder.decompress(path.read_bytes())
        complete = decoded.rsplit(b"\n", 1)[0]
        for line in complete.split(b"\n"):
            yield line.decode("utf-8", errors="replace")
    else:
        with bz2.open(path, "rt", errors="replace") as handle:
            yield from handle


def load_day(day: str, prefix: bool, advertiser_only: bool = False) -> tuple[pd.DataFrame, dict[str, int]]:
    """Parse supported impressions and join click events by bid ID."""
    clicks = click_counts(day)
    records: list[dict[str, object]] = []
    audit = {"rows": 0, "malformed": 0, "invalid_price": 0,
             "invalid_advertiser_price": 0, "advertiser_rows": 0}
    for line in impression_lines(day, prefix):
        audit["rows"] += 1
        fields = line.rstrip("\r\n").split("\t")
        if len(fields) != 24:
            audit["malformed"] += 1
            continue
        try:
            bid, price = int(fields[19]), int(fields[20])
        except ValueError:
            audit["malformed"] += 1
            continue
        if price < 0 or bid < 0 or price > bid:
            audit["invalid_price"] += 1
            if fields[22] == ADVERTISER:
                audit["invalid_advertiser_price"] += 1
            continue
        if fields[22] == ADVERTISER:
            audit["advertiser_rows"] += 1
        if advertiser_only and fields[22] != ADVERTISER:
            continue
        record: dict[str, object] = {
            "bid_id": fields[0], "timestamp": fields[1], "advertiser": fields[22],
            "exchange": fields[8], "region": fields[6], "city": fields[7],
            "domain": fields[9], "slot_id": fields[12], "slot_width": fields[13],
            "slot_height": fields[14], "slot_visibility": fields[15],
            "slot_format": fields[16], "creative": fields[18],
            "hour": fields[1][8:10], "logged_bid": bid, "price": price,
            "clicks": clicks[fields[0]], "clicked": int(clicks[fields[0]] > 0),
        }
        records.append(record)
    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        raise ValueError(f"No valid rows for {day}")
    if not frame["timestamp"].is_monotonic_increasing:
        frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return frame, audit


def encode_features(train: pd.DataFrame, *others: pd.DataFrame) -> list[pd.DataFrame]:
    """Learn categorical vocabularies only on the training partition."""
    output: list[pd.DataFrame] = []
    vocabularies = {
        column: pd.Index(train[column].astype(str).unique()) for column in FEATURE_COLUMNS
    }
    for frame in (train, *others):
        encoded = pd.DataFrame(index=frame.index)
        for column in FEATURE_COLUMNS:
            encoded[column] = pd.Categorical(
                frame[column].astype(str), categories=vocabularies[column]
            ).codes.astype("int32")
        output.append(encoded)
    return output


def train_pctr(train: pd.DataFrame, calibration: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Fit LightGBM on training rows and Platt-calibrate on later rows."""
    x_train, x_cal, x_test = encode_features(train, calibration, test)
    model = lgb.LGBMClassifier(
        n_estimators=160, learning_rate=0.04, num_leaves=15,
        min_child_samples=150, max_depth=5, verbosity=-1,
        random_state=17, n_jobs=4,
    )
    model.fit(x_train, train["clicked"], categorical_feature=list(FEATURE_COLUMNS))
    raw_cal = np.clip(model.predict_proba(x_cal)[:, 1], 1e-7, 1 - 1e-7)
    raw_test = np.clip(model.predict_proba(x_test)[:, 1], 1e-7, 1 - 1e-7)
    logit_cal = np.log(raw_cal / (1 - raw_cal)).reshape(-1, 1)
    logit_test = np.log(raw_test / (1 - raw_test)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e6, max_iter=1000)
    calibrator.fit(logit_cal, calibration["clicked"])
    p_cal = np.clip(calibrator.predict_proba(logit_cal)[:, 1], 1e-8, 1 - 1e-8)
    p_test = np.clip(calibrator.predict_proba(logit_test)[:, 1], 1e-8, 1 - 1e-8)
    diagnostics = {
        "train_rows": len(train), "train_clicked": int(train["clicked"].sum()),
        "calibration_rows": len(calibration),
        "calibration_clicked": int(calibration["clicked"].sum()),
        "calibration_ctr": float(calibration["clicked"].mean()),
        "calibration_mean_pctr": float(p_cal.mean()),
        "calibration_brier": float(brier_score_loss(calibration["clicked"], p_cal)),
        "calibration_logloss": float(log_loss(calibration["clicked"], p_cal)),
        "calibration_auc": float(roc_auc_score(calibration["clicked"], p_cal)),
        "test_rows": len(test), "test_clicked": int(test["clicked"].sum()),
        "test_ctr": float(test["clicked"].mean()),
        "test_mean_pctr": float(p_test.mean()),
        "test_brier": float(brier_score_loss(test["clicked"], p_test)),
        "test_logloss": float(log_loss(test["clicked"], p_test)),
        "test_auc": float(roc_auc_score(test["clicked"], p_test)),
    }
    return p_cal, p_test, diagnostics


def to_auctions(frame: pd.DataFrame, probabilities: np.ndarray) -> list[Auction]:
    """Construct one advertiser's chronological supported auction sequence."""
    chosen = frame["advertiser"].to_numpy() == ADVERTISER
    subset = frame.loc[chosen]
    probs = probabilities[chosen]
    return [
        Auction(str(row.timestamp), int(row.price), int(row.logged_bid),
                int(row.clicks), float(prob))
        for row, prob in zip(subset.itertuples(), probs, strict=True)
    ]


def conditional_win_curve(prices: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Fit ORTB's hyperbolic curve to logged winning-price CDF."""
    bids = np.linspace(0, float(np.percentile(prices, 99.5)), 100)
    empirical = np.searchsorted(np.sort(prices), bids, side="right") / len(prices)
    fit = least_squares(
        lambda param: bids / (param[0] + bids + 1e-12) - empirical,
        x0=[max(float(np.median(prices)), 1.0)], bounds=(1e-6, np.inf),
    )
    return bids, empirical, float(fit.x[0])


def bid_value(strategy: str, pctr: float, scale: float, avg_pctr: float, c: float) -> float:
    """Return constant, linear, or ORTB bid in logged CPM price units."""
    if strategy == "constant":
        return scale
    if strategy == "linear":
        return scale * pctr / avg_pctr
    if strategy in ("ortb", "paced_ortb"):
        return math.sqrt(c * c + c * scale * pctr / avg_pctr) - c
    raise ValueError(f"Unknown strategy {strategy}")


def supported_bid(auction: Auction, desired_bid: float) -> float:
    """Restrict counterfactual bidding to the original logged bid support."""
    return min(max(desired_bid, 0.0), float(auction.logged_bid))


def tune_scale(strategy: str, auctions: list[Auction], target_spend: float, avg_pctr: float, c: float) -> float:
    """Find the largest monotone scale near a calibration spend target."""
    if not auctions:
        raise ValueError("Calibration auctions required")

    def spend(scale: float) -> float:
        """Calculate uncapped spend on calibration auctions."""
        return sum(
            auction.price / PRICE_SCALE for auction in auctions
            if supported_bid(auction, bid_value(strategy, auction.pctr, scale, avg_pctr, c)) >= auction.price
        )

    low, high = 0.0, 1.0
    while spend(high) < target_spend and high < 1e8:
        high *= 2.0
    for _ in range(35):
        middle = (low + high) / 2.0
        if spend(middle) <= target_spend:
            low = middle
        else:
            high = middle
    return low


def replay(strategy: str, auctions: list[Auction], budget: float, scale: float, avg_pctr: float, c: float) -> Score:
    """Replay ordered logged wins with second-price cost and a hard budget."""
    spend = 0.0
    clicks = wins = clicked_impressions = 0
    hourly = [0.0] * HOURS
    for auction in auctions:
        hour = int(auction.timestamp[8:10])
        multiplier = 1.0
        if strategy == "paced_ortb":
            minute = int(auction.timestamp[10:12])
            second = int(auction.timestamp[12:14])
            elapsed = hour + minute / 60 + second / 3600
            target = budget * elapsed / HOURS
            error = (target - spend) / max(budget / HOURS, 1e-12)
            multiplier = float(np.clip(1 + PACING_GAIN * error, PACING_MIN, PACING_MAX))
        desired = bid_value(strategy, auction.pctr, scale, avg_pctr, c) * multiplier
        bid = supported_bid(auction, desired)
        cost = auction.price / PRICE_SCALE
        if bid >= auction.price and spend + cost <= budget + 1e-9:
            spend += cost
            hourly[hour] += cost
            clicks += auction.clicks
            clicked_impressions += int(auction.clicks > 0)
            wins += 1
    return Score(strategy, clicks, clicked_impressions, spend,
                 spend / clicks if clicks else None, wins, budget, hourly)


def plot_results(scores: list[Score], bids: np.ndarray, empirical: np.ndarray, c: float) -> None:
    """Save hourly cumulative spend and observed conditional eligibility plots."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    for score in scores:
        ax.plot(range(HOURS + 1), [0, *np.cumsum(score.hourly_spend)], label=score.strategy)
    ax.plot(range(HOURS + 1), np.linspace(0, scores[0].budget, HOURS + 1),
            "k--", label="uniform budget target")
    ax.set(xlabel="Hour boundary", ylabel="Cumulative spend (logged price units)",
           title="Supported auction replay: cumulative spend")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "hourly_spend.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(bids, empirical, label="empirical logged-price CDF")
    ax.plot(bids, bids / (c + bids), label="ORTB hyperbolic fit")
    ax.set(xlabel="Bid (logged CPM price units)", ylabel="Conditional eligibility",
           title="Observed winning-price curve")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "win_curve.png", dpi=160)
    plt.close(fig)


def run() -> dict[str, object]:
    """Run the entire fixed-partition experiment and persist audit artifacts."""
    for spec in FILES:
        path = RAW / spec.name
        if not path.exists() or path.stat().st_size != spec.end - spec.start + 1:
            raise FileNotFoundError(f"Missing or incomplete source: {path}")
        if digest_file(path, spec.algorithm) != spec.digest:
            raise ValueError(f"Source checksum mismatch: {path}")
    frames: dict[str, pd.DataFrame] = {}
    audits: dict[str, dict[str, int]] = {}
    for day in (*TRAIN_DAYS, CAL_DAY, TEST_DAY):
        frame, audit = load_day(day, day != TEST_DAY, day == TEST_DAY)
        frames[day], audits[day] = frame, audit
        print(f"Loaded {day}: {audit}", flush=True)
    train = pd.concat([frames[day] for day in TRAIN_DAYS], ignore_index=True)
    calibration, test = frames[CAL_DAY], frames[TEST_DAY]
    p_cal, p_test, diagnostics = train_pctr(train, calibration, test)
    cal_auctions = to_auctions(calibration, p_cal)
    test_auctions = to_auctions(test, p_test)
    train_advertiser = train.loc[train["advertiser"] == ADVERTISER]
    historical_prefix_spend = [
        float(frames[day].loc[frames[day]["advertiser"] == ADVERTISER, "price"].sum()) / PRICE_SCALE
        for day in TRAIN_DAYS
    ]
    observed_hours = [
        (int(frames[day]["timestamp"].iloc[-1][8:10]) + 1) for day in TRAIN_DAYS
    ]
    budget = float(np.mean([spend / hours * HOURS for spend, hours in zip(historical_prefix_spend, observed_hours, strict=True)])) * BUDGET_FRACTION
    cal_hours = int(calibration["timestamp"].iloc[-1][8:10]) + 1
    cal_target = budget * cal_hours / HOURS
    prices = train_advertiser["price"].to_numpy()
    bids, empirical, c = conditional_win_curve(prices)
    win_curve_rmse = float(np.sqrt(np.mean((bids / (c + bids) - empirical) ** 2)))
    avg_pctr = float(np.mean([auction.pctr for auction in cal_auctions]))
    strategies = ("constant", "linear", "ortb", "paced_ortb")
    scales = {
        name: tune_scale("ortb" if name == "paced_ortb" else name,
                         cal_auctions, cal_target, avg_pctr, c)
        for name in strategies
    }
    scores = [replay(name, test_auctions, budget, scales[name], avg_pctr, c) for name in strategies]
    plot_results(scores, bids, empirical, c)
    RESULTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "strategy": score.strategy, "clicks": score.clicks,
        "clicked_impressions": score.clicked_impressions, "spend": score.spend,
        "ecpc": score.ecpc, "wins": score.wins, "budget": score.budget,
    } for score in scores]).to_csv(RESULTS / "strategy_comparison.csv", index=False)
    pd.DataFrame({"hour": list(range(HOURS)), **{
        score.strategy: score.hourly_spend for score in scores
    }}).to_csv(RESULTS / "hourly_spend.csv", index=False)
    pd.DataFrame({"bid": bids, "empirical": empirical,
                  "fitted": bids / (c + bids)}).to_csv(RESULTS / "win_curve.csv", index=False)
    report: dict[str, object] = {
        "audits": audits, "model": diagnostics, "advertiser": ADVERTISER,
        "historical_prefix_spend": historical_prefix_spend,
        "observed_train_hours": observed_hours,
        "budget_fraction": BUDGET_FRACTION, "budget": budget,
        "calibration_target": cal_target, "calibration_hours": cal_hours,
        "win_curve_c": c, "win_curve_rmse": win_curve_rmse,
        "mean_calibration_pctr_for_advertiser": avg_pctr,
        "scales": scales, "scores": [asdict(score) for score in scores],
        "test_advertiser_rows": len(test_auctions),
        "test_advertiser_clicked_impressions": sum(a.clicks > 0 for a in test_auctions),
        "test_advertiser_click_events": sum(a.clicks for a in test_auctions),
    }
    (RESULTS / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
