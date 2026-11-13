"""Train LightGBM models on the feature frame and evaluate them against a simple baseline.

Two boosters are trained, one for PPR and one for standard scoring; half-PPR is their average.
Training on ~50k player-weeks takes seconds on a single CPU, so no GPU is needed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

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


@dataclass
class TrainedModels:
    boosters: dict[str, lgb.Booster]
    training_rows: int
    training_seconds: float

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        X = frame[FEATURES]
        out = pd.DataFrame(index=frame.index)
        for fmt, booster in self.boosters.items():
            out[fmt] = np.clip(booster.predict(X), 0, None)
        out["half"] = (out["ppr"] + out["std"]) / 2
        return out.round(2)

    def to_text(self) -> dict[str, str]:
        return {fmt: b.model_to_string() for fmt, b in self.boosters.items()}

    @classmethod
    def from_text(cls, texts: dict[str, str]) -> TrainedModels:
        return cls({fmt: lgb.Booster(model_str=t) for fmt, t in texts.items()}, 0, 0.0)

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


def train(frame: pd.DataFrame, num_rounds: int = NUM_ROUNDS) -> TrainedModels:
    rows = training_rows(frame)
    if rows.empty:
        raise ValueError("No training rows available")
    start = time.perf_counter()
    boosters = {}
    for fmt, target in TARGETS.items():
        dataset = lgb.Dataset(
            rows[FEATURES], label=rows[target], categorical_feature=CATEGORICAL_FEATURES, free_raw_data=True
        )
        boosters[fmt] = lgb.train(PARAMS, dataset, num_boost_round=num_rounds)
    return TrainedModels(boosters, len(rows), round(time.perf_counter() - start, 2))


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
