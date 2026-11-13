"""Feature engineering for weekly fantasy point predictions.

Every feature for a (player, season, week) row is computed only from games *before* that week, so the
same code builds training rows (past games with known scores) and rows for the upcoming week.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .models import POSITIONS

POSITION_CODES = {pos: i for i, pos in enumerate(POSITIONS)}

USAGE_COLUMNS = [
    "fantasy_points_ppr",
    "fantasy_points_std",
    "targets",
    "receptions",
    "carries",
    "attempts",
    "passing_yards",
    "rushing_yards",
    "receiving_yards",
    "target_share",
]

FEATURES = [
    "position_code",
    "is_home",
    "implied_team_total",
    "team_spread",
    "game_total",
    "ppr_last1",
    "ppr_last3",
    "ppr_last5",
    "ppr_last10",
    "ppr_std5",
    "std_last5",
    "ppr_season_avg",
    "ppr_prev_season_avg",
    "games_this_season",
    "career_games",
    "weeks_since_last_game",
    "targets_last3",
    "receptions_last3",
    "carries_last3",
    "attempts_last3",
    "passing_yards_last3",
    "rushing_yards_last3",
    "receiving_yards_last3",
    "target_share_last3",
    "opp_allowed_ppr_last8",
    "opp_allowed_ppr_season",
]
CATEGORICAL_FEATURES = ["position_code"]


def team_games(games: pd.DataFrame) -> pd.DataFrame:
    """Turn one row per game into one row per team-game, with Vegas-implied team totals."""
    g = games.copy()
    spread = g["spread_line"].astype(float)
    total = g["total_line"].astype(float)
    home = pd.DataFrame(
        {
            "season": g["season"],
            "week": g["week"],
            "team": g["home_team"],
            "opponent": g["away_team"],
            "is_home": 1,
            "team_spread": spread,
            "game_total": total,
            "implied_team_total": (total + spread) / 2,
        }
    )
    away = pd.DataFrame(
        {
            "season": g["season"],
            "week": g["week"],
            "team": g["away_team"],
            "opponent": g["home_team"],
            "is_home": 0,
            "team_spread": -spread,
            "game_total": total,
            "implied_team_total": (total - spread) / 2,
        }
    )
    return pd.concat([home, away], ignore_index=True)


def _week_index(season: pd.Series, week: pd.Series) -> pd.Series:
    """A monotonically increasing game-time index across seasons (18 regular-season weeks max)."""
    return season.astype(int) * 100 + week.astype(int)


def opponent_allowed(stats: pd.DataFrame) -> pd.DataFrame:
    """Fantasy points each defense allowed to each position per game, with rolling averages.

    The rolling values *include* the game on that row; callers look them up strictly before the
    week being predicted.
    """
    allowed = (
        stats.groupby(["opponent", "position", "season", "week"], as_index=False)["fantasy_points_ppr"]
        .sum()
        .rename(columns={"fantasy_points_ppr": "allowed"})
        .sort_values(["opponent", "position", "season", "week"])
    )
    grp = allowed.groupby(["opponent", "position"])["allowed"]
    allowed["opp_allowed_ppr_last8"] = grp.transform(lambda s: s.rolling(8, min_periods=1).mean())
    allowed["opp_allowed_ppr_season"] = allowed.groupby(["opponent", "position", "season"])["allowed"].transform(
        lambda s: s.expanding().mean()
    )
    allowed["t"] = _week_index(allowed["season"], allowed["week"])
    return allowed


def build_features(stats: pd.DataFrame, games: pd.DataFrame, upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the feature frame.

    ``stats`` holds played games (one row per player-week, with fantasy points).
    ``upcoming`` optionally holds rows to predict, with columns player_id, season, week, team,
    opponent, position. Their fantasy points are NaN in the output.
    """
    played = stats.copy()
    played["is_played"] = True
    frames = [played]
    if upcoming is not None and len(upcoming):
        up = upcoming[["player_id", "season", "week", "team", "opponent", "position"]].copy()
        up["is_played"] = False
        frames.append(up)
    df = pd.concat(frames, ignore_index=True)
    for col in USAGE_COLUMNS:
        if col not in df:
            df[col] = np.nan
        df[col] = df[col].astype(float)

    df["t"] = _week_index(df["season"], df["week"])
    df = df.sort_values(["player_id", "t"]).reset_index(drop=True)
    by_player = df.groupby("player_id", sort=False)

    # Rolling form over previous games (shift(1) so the current week never leaks into its own features).
    prev_ppr = by_player["fantasy_points_ppr"].shift(1)
    df["_prev_ppr"] = prev_ppr
    roll = df.groupby("player_id", sort=False)["_prev_ppr"]
    df["ppr_last1"] = prev_ppr
    df["ppr_last3"] = roll.transform(lambda s: s.rolling(3, min_periods=1).mean())
    df["ppr_last5"] = roll.transform(lambda s: s.rolling(5, min_periods=1).mean())
    df["ppr_last10"] = roll.transform(lambda s: s.rolling(10, min_periods=1).mean())
    df["ppr_std5"] = roll.transform(lambda s: s.rolling(5, min_periods=2).std())

    for col, name in [
        ("fantasy_points_std", "std_last5"),
        ("targets", "targets_last3"),
        ("receptions", "receptions_last3"),
        ("carries", "carries_last3"),
        ("attempts", "attempts_last3"),
        ("passing_yards", "passing_yards_last3"),
        ("rushing_yards", "rushing_yards_last3"),
        ("receiving_yards", "receiving_yards_last3"),
        ("target_share", "target_share_last3"),
    ]:
        window = 5 if name.endswith("5") else 3
        df["_tmp"] = by_player[col].shift(1)
        df[name] = df.groupby("player_id", sort=False)["_tmp"].transform(
            lambda s, w=window: s.rolling(w, min_periods=1).mean()
        )

    by_season = df.groupby(["player_id", "season"], sort=False)
    df["_prev_ppr_season"] = by_season["fantasy_points_ppr"].shift(1)
    df["ppr_season_avg"] = df.groupby(["player_id", "season"], sort=False)["_prev_ppr_season"].transform(
        lambda s: s.expanding().mean()
    )
    df["games_this_season"] = by_season.cumcount()
    df["career_games"] = by_player.cumcount()

    prev_t = by_player["t"].shift(1)
    # Convert the season*100+week index into elapsed weeks (a season is ~18 weeks plus offseason gap).
    df["weeks_since_last_game"] = np.where(
        prev_t.isna(),
        np.nan,
        (df["season"] - prev_t // 100) * 18 + (df["week"] - prev_t % 100),
    )

    season_avgs = (
        played.groupby(["player_id", "season"])["fantasy_points_ppr"].mean().rename("ppr_prev_season_avg").reset_index()
    )
    season_avgs["season"] = season_avgs["season"] + 1
    df = df.merge(season_avgs, on=["player_id", "season"], how="left")

    # Game context from the schedule.
    tg = team_games(games)
    df = df.merge(tg.drop(columns=["opponent"]), on=["season", "week", "team"], how="left")
    df["is_home"] = df["is_home"].astype(float)

    # Strength of the opposing defense against this position, using only earlier weeks.
    allowed = opponent_allowed(played)
    lookup = allowed[["opponent", "position", "t", "opp_allowed_ppr_last8", "opp_allowed_ppr_season", "season"]]
    lookup = lookup.rename(columns={"season": "_allowed_season"}).sort_values("t")
    df = df.sort_values("t")
    df = pd.merge_asof(
        df,
        lookup,
        on="t",
        by=["opponent", "position"],
        allow_exact_matches=False,
        direction="backward",
    )
    # Season-to-date allowed only applies within the same season.
    df.loc[df["_allowed_season"] != df["season"], "opp_allowed_ppr_season"] = np.nan

    df["position_code"] = df["position"].map(POSITION_CODES).astype(float)
    df["fantasy_points_half"] = (df["fantasy_points_ppr"] + df["fantasy_points_std"]) / 2
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
    return df.sort_values(["season", "week", "player_id"]).reset_index(drop=True)
