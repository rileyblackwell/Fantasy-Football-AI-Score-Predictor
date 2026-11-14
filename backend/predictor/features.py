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
    "offense_snap_pct",
    "expected_ppr",
    "air_yards",
]

# Official game-status designations, as a number (0 = not on the report).
INJURY_LEVELS = {"Questionable": 1, "Doubtful": 2, "Out": 3}

FEATURES = [
    "position_code",
    "is_home",
    "implied_team_total",
    "opp_implied_total",
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
    # Longer-run form: a smoothed recent average, a 20-game window, career and two-season baselines.
    "ppr_ewm4",
    "ppr_last20",
    "ppr_career_avg",
    "ppr_prev2_avg",
    # Role: share of the offense's snaps, and expected points from the volume and quality of looks.
    "snap_last1",
    "snap_last3",
    "xfp_last3",
    "xfp_last6",
    "air_yards_last3",
    # This week's injury report: the player's own status and the workload of teammates ruled out.
    "inj_status",
    "vacated_ppr_pos",
    "vacated_targets",
    "vacated_carries",
    # Career stage.
    "age",
    "nfl_year",
    "draft_pick",
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
            "opp_implied_total": (total - spread) / 2,
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
            "opp_implied_total": (total + spread) / 2,
        }
    )
    return pd.concat([home, away], ignore_index=True)


def _rolling_mean(df: pd.DataFrame, keys, col: str, window: int, min_periods: int = 1) -> pd.Series:
    """Rolling mean of ``col`` within each group, aligned to ``df``'s index (vectorized, no lambdas)."""
    out = df.groupby(keys, sort=False)[col].rolling(window, min_periods=min_periods).mean()
    return out.reset_index(level=list(range(out.index.nlevels - 1)), drop=True)


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
        .reset_index(drop=True)
    )
    allowed["opp_allowed_ppr_last8"] = _rolling_mean(allowed, ["opponent", "position"], "allowed", 8)
    season_grp = allowed.groupby(["opponent", "position", "season"], sort=False)["allowed"]
    allowed["opp_allowed_ppr_season"] = season_grp.cumsum() / (season_grp.cumcount() + 1)
    allowed["t"] = _week_index(allowed["season"], allowed["week"])
    return allowed


def _injury_features(df: pd.DataFrame, played: pd.DataFrame, injuries: pd.DataFrame | None) -> pd.DataFrame:
    """The player's own game status this week, and the recent workload of teammates ruled out.

    A teammate counts as ruled out when listed Out or Doubtful for the week. Their workload is the
    average over their last four games (as of before this week), counted only if they played this
    season or last, and credited to the team they last played for.
    """
    cols = ["inj_status", "vacated_ppr_pos", "vacated_targets", "vacated_carries"]
    if injuries is None or injuries.empty:
        for col in cols:
            df[col] = 0.0
        return df
    inj = injuries[["player_id", "season", "week", "status"]].copy()
    inj["level"] = inj["status"].map(INJURY_LEVELS).fillna(0).astype(float)
    inj = inj.sort_values("level").drop_duplicates(["player_id", "season", "week"], keep="last")
    df = df.merge(
        inj[["player_id", "season", "week", "level"]].rename(columns={"level": "inj_status"}),
        on=["player_id", "season", "week"],
        how="left",
    )
    df["inj_status"] = df["inj_status"].fillna(0.0)

    work = played[["player_id", "season", "week", "team", "position", "fantasy_points_ppr", "targets", "carries"]]
    work = work.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    for col in ["fantasy_points_ppr", "targets", "carries"]:
        work[col] = work[col].astype(float)
        work["w_" + col] = _rolling_mean(work, "player_id", col, 4)
    work["t"] = _week_index(work["season"], work["week"]).astype("int64")
    work = work.rename(columns={"season": "_last_season"}).sort_values("t")

    out = inj[inj["level"] >= 2].copy()
    out["t"] = _week_index(out["season"], out["week"]).astype("int64")
    out = pd.merge_asof(
        out.sort_values("t"),
        work[["player_id", "t", "_last_season", "team", "position", "w_fantasy_points_ppr", "w_targets", "w_carries"]],
        on="t",
        by="player_id",
        allow_exact_matches=False,
        direction="backward",
    )
    out = out[out["_last_season"] >= out["season"] - 1]
    by_pos = (
        out.groupby(["team", "season", "week", "position"], as_index=False)["w_fantasy_points_ppr"]
        .sum()
        .rename(columns={"w_fantasy_points_ppr": "vacated_ppr_pos"})
    )
    by_team = (
        out.groupby(["team", "season", "week"], as_index=False)[["w_targets", "w_carries"]]
        .sum()
        .rename(columns={"w_targets": "vacated_targets", "w_carries": "vacated_carries"})
    )
    df = df.merge(by_pos, on=["team", "season", "week", "position"], how="left")
    df = df.merge(by_team, on=["team", "season", "week"], how="left")
    for col in cols[1:]:
        df[col] = df[col].astype(float).fillna(0.0)
    return df


def _career_features(df: pd.DataFrame, players: pd.DataFrame | None) -> pd.DataFrame:
    """Age at the season's midpoint, years in the league and draft slot (undrafted players stay empty)."""
    if players is None or players.empty:
        for col in ["age", "nfl_year", "draft_pick"]:
            df[col] = np.nan
        return df
    bio = players[["player_id", "birth_date", "rookie_season", "draft_pick"]].drop_duplicates("player_id")
    df = df.merge(bio, on="player_id", how="left")
    born = pd.to_datetime(df["birth_date"], errors="coerce")
    df["age"] = df["season"] + 0.75 - (born.dt.year + born.dt.day_of_year / 365.25)
    df["nfl_year"] = df["season"] - pd.to_numeric(df["rookie_season"], errors="coerce")
    df["draft_pick"] = pd.to_numeric(df["draft_pick"], errors="coerce")
    return df.drop(columns=["birth_date", "rookie_season"])


def build_features(
    stats: pd.DataFrame,
    games: pd.DataFrame,
    upcoming: pd.DataFrame | None = None,
    players: pd.DataFrame | None = None,
    injuries: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the feature frame.

    ``stats`` holds played games (one row per player-week, with fantasy points).
    ``upcoming`` optionally holds rows to predict, with columns player_id, season, week, team,
    opponent, position. Their fantasy points are NaN in the output.
    ``players`` optionally holds birth_date, rookie_season and draft_pick per player_id, and
    ``injuries`` the weekly injury report (player_id, season, week, status). Without them those
    features are left empty and the model works from the rest.
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

    # Each stat shifted by one game, so the current week never leaks into its own features.
    prev = {col: by_player[col].shift(1) for col in USAGE_COLUMNS}
    for col, series in prev.items():
        df["_prev_" + col] = series

    def roll(col: str, window: int, min_periods: int = 1) -> pd.Series:
        return _rolling_mean(df, "player_id", "_prev_" + col, window, min_periods)

    df["ppr_last1"] = prev["fantasy_points_ppr"]
    df["ppr_last3"] = roll("fantasy_points_ppr", 3)
    df["ppr_last5"] = roll("fantasy_points_ppr", 5)
    df["ppr_last10"] = roll("fantasy_points_ppr", 10)
    df["ppr_last20"] = roll("fantasy_points_ppr", 20)
    std5 = df.groupby("player_id", sort=False)["_prev_fantasy_points_ppr"].rolling(5, min_periods=2).std()
    df["ppr_std5"] = std5.reset_index(level=0, drop=True)
    ewm = df.groupby("player_id", sort=False)["_prev_fantasy_points_ppr"].ewm(halflife=4, ignore_na=True).mean()
    df["ppr_ewm4"] = ewm.reset_index(level=0, drop=True)
    prev_grp = df.groupby("player_id", sort=False)["_prev_fantasy_points_ppr"]
    df["ppr_career_avg"] = prev_grp.cumsum() / prev_grp.cumcount().where(lambda n: n > 0)
    df["std_last5"] = roll("fantasy_points_std", 5)
    for col in ["targets", "receptions", "carries", "attempts", "passing_yards", "rushing_yards",
                "receiving_yards", "target_share", "air_yards"]:
        df[f"{col}_last3"] = roll(col, 3)
    df["snap_last1"] = prev["offense_snap_pct"]
    df["snap_last3"] = roll("offense_snap_pct", 3)
    df["xfp_last3"] = roll("expected_ppr", 3)
    df["xfp_last6"] = roll("expected_ppr", 6)

    by_season = df.groupby(["player_id", "season"], sort=False)
    df["_prev_ppr_season"] = by_season["fantasy_points_ppr"].shift(1)
    season_prev = df.groupby(["player_id", "season"], sort=False)["_prev_ppr_season"]
    df["ppr_season_avg"] = season_prev.cumsum() / season_prev.cumcount().where(lambda n: n > 0)
    df["games_this_season"] = by_season.cumcount()
    df["career_games"] = by_player.cumcount()

    prev_t = by_player["t"].shift(1)
    # Convert the season*100+week index into elapsed weeks (a season is ~18 weeks plus offseason gap).
    df["weeks_since_last_game"] = np.where(
        prev_t.isna(),
        np.nan,
        (df["season"] - prev_t // 100) * 18 + (df["week"] - prev_t % 100),
    )

    # Per-game averages for last season, and for the last two seasons together.
    totals = played.groupby(["player_id", "season"])["fantasy_points_ppr"].agg(["sum", "count"]).reset_index()
    last1 = totals.assign(season=totals["season"] + 1)
    last2 = totals.assign(season=totals["season"] + 2)
    seasons = last1.merge(last2, on=["player_id", "season"], how="outer", suffixes=("_1", "_2"))
    seasons["ppr_prev_season_avg"] = seasons["sum_1"] / seasons["count_1"]
    filled = seasons.fillna({"sum_1": 0, "count_1": 0, "sum_2": 0, "count_2": 0})
    seasons["ppr_prev2_avg"] = (filled["sum_1"] + filled["sum_2"]) / (filled["count_1"] + filled["count_2"])
    df = df.merge(seasons[["player_id", "season", "ppr_prev_season_avg", "ppr_prev2_avg"]], on=["player_id", "season"], how="left")

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

    df = _injury_features(df, played, injuries)
    df = _career_features(df, players)

    df["position_code"] = df["position"].map(POSITION_CODES).astype(float)
    df["fantasy_points_half"] = (df["fantasy_points_ppr"] + df["fantasy_points_std"]) / 2
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
    return df.sort_values(["season", "week", "player_id"]).reset_index(drop=True)
