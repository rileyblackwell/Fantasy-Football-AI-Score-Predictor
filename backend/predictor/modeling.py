"""Train LightGBM models on the feature frame and evaluate them against a simple baseline.

Two boosters are trained, one for PPR and one for standard scoring; half-PPR is their average. The model
that projects the upcoming week also gets quantile boosters for each format's 10th-90th percentile range.
Training on ~50k player-weeks takes seconds on a single CPU, so no GPU is needed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import CATEGORICAL_FEATURES, FEATURES
from .models import POSITIONS

TARGETS = {"ppr": "fantasy_points_ppr", "std": "fantasy_points_std"}

PARAMS = {
    # Huber loss: fantasy scores have long right tails (multi-TD games), so plain squared error lets
    # outliers drag the fit around. Huber cut held-out error ~2% vs L2 while staying close to a mean
    # projection (pure L1 scored lower error but projects medians, which run low).
    "objective": "huber",
    "alpha": 8.0,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 40,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "num_threads": 2,
    "verbosity": -1,
    "seed": 7,
}
NUM_ROUNDS = 500

# Score ranges: two quantile boosters per scoring format give the 10th and 90th percentile outcome, so
# about 8 weeks in 10 land inside the range. Tested out of sample on 2025 and 2026: ~78% of actual
# scores landed inside, and this beat ranges built from each position's past misses. They are trained
# for the final model only (the one that projects the upcoming week), which adds a few seconds per run.
RANGE_QUANTILES = {"q10": 0.1, "q90": 0.9}
RANGE_PARAMS = {**{k: v for k, v in PARAMS.items() if k != "alpha"}, "objective": "quantile", "learning_rate": 0.05}
RANGE_ROUNDS = 200

# How swingy a projection is: the width of its range divided by the projection (PPR). Fantasy scores
# swing a lot for everyone (a 15-point WR's range is about 6 to 26), so these cut-offs split the
# start-worthy players into rough thirds rather than promising anyone a tight range.
STEADY_MAX_SWING = 1.4
SWINGY_MAX_SWING = 1.9


def consistency(projection: float | None, floor: float | None, ceiling: float | None) -> str | None:
    """'steady', 'swingy' or 'boom_bust' from a projection and its 10th-90th percentile range."""
    if projection is None or floor is None or ceiling is None:
        return None
    swing = (ceiling - floor) / max(projection, 1.0)
    if swing < STEADY_MAX_SWING:
        return "steady"
    if swing < SWINGY_MAX_SWING:
        return "swingy"
    return "boom_bust"


@dataclass
class TrainedModels:
    boosters: dict[str, lgb.Booster]
    training_rows: int
    training_seconds: float
    # Quantile boosters keyed like "ppr_q10"; empty when the model was trained without ranges.
    range_boosters: dict[str, lgb.Booster] = field(default_factory=dict)

    @property
    def has_ranges(self) -> bool:
        return all(f"{fmt}_{q}" in self.range_boosters for fmt in TARGETS for q in RANGE_QUANTILES)

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Projections per format ("ppr", "half", "std"), plus "floor_<fmt>" and "ceiling_<fmt>" when the
        model has ranges. A range always contains its projection and never drops below zero."""
        X = frame[FEATURES]
        out = pd.DataFrame(index=frame.index)
        for fmt, booster in self.boosters.items():
            out[fmt] = np.clip(booster.predict(X), 0, None)
        out["half"] = (out["ppr"] + out["std"]) / 2
        if self.has_ranges:
            for fmt in TARGETS:
                low = np.clip(self.range_boosters[f"{fmt}_q10"].predict(X), 0, None)
                high = self.range_boosters[f"{fmt}_q90"].predict(X)
                out[f"floor_{fmt}"] = np.minimum(low, out[fmt])
                out[f"ceiling_{fmt}"] = np.maximum(high, out[fmt])
            out["floor_half"] = (out["floor_ppr"] + out["floor_std"]) / 2
            out["ceiling_half"] = (out["ceiling_ppr"] + out["ceiling_std"]) / 2
        return out.round(2)

    def to_text(self) -> dict[str, str]:
        boosters = {**self.boosters, **self.range_boosters}
        return {key: b.model_to_string() for key, b in boosters.items()}

    @classmethod
    def from_text(cls, texts: dict[str, str]) -> TrainedModels:
        boosters = {key: lgb.Booster(model_str=t) for key, t in texts.items()}
        ranges = {key: b for key, b in boosters.items() if key not in TARGETS}
        return cls({key: b for key, b in boosters.items() if key in TARGETS}, 0, 0.0, ranges)

    def feature_importance(self, top: int = 12) -> list[dict]:
        booster = self.boosters["ppr"]
        gains = booster.feature_importance(importance_type="gain")
        total = gains.sum() or 1.0
        pairs = sorted(zip(booster.feature_name(), gains), key=lambda p: p[1], reverse=True)[:top]
        return [{"feature": name, "share": round(float(g / total), 4)} for name, g in pairs]


def training_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Played games with at least one earlier game for the player (rows with no history teach nothing)."""
    rows = frame[frame["is_played"].astype(bool) & frame["career_games"].gt(0)]
    return rows.dropna(subset=list(TARGETS.values()))


def train(frame: pd.DataFrame, num_rounds: int = NUM_ROUNDS, with_ranges: bool = False) -> TrainedModels:
    """Train the projection boosters, and with ``with_ranges`` the 10th/90th percentile boosters too."""
    rows = training_rows(frame)
    if rows.empty:
        raise ValueError("No training rows available")
    start = time.perf_counter()

    def dataset(target: str) -> lgb.Dataset:
        return lgb.Dataset(
            rows[FEATURES], label=rows[target], categorical_feature=CATEGORICAL_FEATURES, free_raw_data=True
        )

    boosters, ranges = {}, {}
    for fmt, target in TARGETS.items():
        boosters[fmt] = lgb.train(PARAMS, dataset(target), num_boost_round=num_rounds)
        if with_ranges:
            for name, alpha in RANGE_QUANTILES.items():
                params = {**RANGE_PARAMS, "alpha": alpha}
                ranges[f"{fmt}_{name}"] = lgb.train(params, dataset(target), num_boost_round=min(RANGE_ROUNDS, num_rounds))
    return TrainedModels(boosters, len(rows), round(time.perf_counter() - start, 2), ranges)


def baseline(frame: pd.DataFrame) -> pd.Series:
    """What a person might guess: season average so far, else last-5 average, else last season's average."""
    return frame["ppr_season_avg"].fillna(frame["ppr_last5"]).fillna(frame["ppr_prev_season_avg"])


def evaluate(frame: pd.DataFrame, holdout_season: int, num_rounds: int = NUM_ROUNDS) -> dict:
    """Train on seasons before ``holdout_season`` and score PPR predictions on that whole season."""
    train_frame = frame[frame["season"] < holdout_season]
    test = training_rows(frame[frame["season"] == holdout_season])
    if training_rows(train_frame).empty or test.empty:
        return {}
    models = train(train_frame, num_rounds=num_rounds)
    test = test.assign(pred=models.predict(test)["ppr"].values, base=baseline(test).values)
    test = test.dropna(subset=["base"])

    def mae(df: pd.DataFrame, col: str) -> float:
        return round(float((df[col] - df["fantasy_points_ppr"]).abs().mean()), 3)

    by_position = {}
    for pos in POSITIONS:
        part = test[test["position"] == pos]
        if len(part):
            by_position[pos] = {"rows": int(len(part)), "model_mae": mae(part, "pred"), "baseline_mae": mae(part, "base")}
    return {
        "holdout_season": int(holdout_season),
        "rows": int(len(test)),
        "model_mae": mae(test, "pred"),
        "baseline_mae": mae(test, "base"),
        "by_position": by_position,
    }
