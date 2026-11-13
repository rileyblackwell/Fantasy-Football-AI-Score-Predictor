"""Train models from the database and write predictions for the upcoming week (plus a backtest)."""

from __future__ import annotations

import logging

import pandas as pd
from django.db import transaction
from django.db.models import Max, Min

from .features import build_features
from .modeling import TrainedModels, evaluate, train
from .models import POSITIONS, Game, ModelRun, Player, Prediction, WeeklyStat

logger = logging.getLogger(__name__)

STAT_FIELDS = [
    "player_id", "season", "week", "team", "opponent", "position", "completions", "attempts", "passing_yards",
    "passing_tds", "interceptions", "carries", "rushing_yards", "rushing_tds", "targets", "receptions",
    "receiving_yards", "receiving_tds", "target_share", "fantasy_points_std", "fantasy_points_ppr",
]
KEEP_RUNS = 5
GAME_FIELDS = ["season", "week", "home_team", "away_team", "spread_line", "total_line", "home_score"]


def stats_frame() -> pd.DataFrame:
    return pd.DataFrame.from_records(WeeklyStat.objects.values(*STAT_FIELDS), columns=STAT_FIELDS)


def games_frame() -> pd.DataFrame:
    return pd.DataFrame.from_records(Game.objects.values(*GAME_FIELDS), columns=GAME_FIELDS)


def target_week() -> tuple[int, int] | None:
    """The earliest week of the latest season that still has an unplayed game, or None if it is over."""
    latest = Game.objects.aggregate(s=Max("season"))["s"]
    if latest is None:
        return None
    week = Game.objects.filter(season=latest, home_score__isnull=True).aggregate(w=Min("week"))["w"]
    return (latest, week) if week is not None else None


def upcoming_rows(season: int, week: int, stats: pd.DataFrame) -> pd.DataFrame:
    """Players to project for ``week``: active rostered QB/RB/WR/TE on a team that plays that week,
    who have played in this season or last season."""
    games = Game.objects.filter(season=season, week=week)
    matchups = {}
    for g in games:
        matchups[g.home_team] = g.away_team
        matchups[g.away_team] = g.home_team

    recent_ids = set(stats.loc[stats["season"] >= season - 1, "player_id"])
    players = Player.objects.filter(position__in=POSITIONS, team__in=matchups.keys())
    has_roster_status = Player.objects.exclude(roster_status="").exists()
    if has_roster_status:
        players = players.filter(roster_status="ACT")
    rows = [
        {
            "player_id": p.player_id,
            "season": season,
            "week": week,
            "team": p.team,
            "opponent": matchups[p.team],
            "position": p.position,
        }
        for p in players
        if p.player_id in recent_ids
    ]
    upcoming = pd.DataFrame(rows, columns=["player_id", "season", "week", "team", "opponent", "position"])
    # A player whose game this week is already final has a real stat row; don't duplicate it.
    played_now = set(stats.loc[(stats["season"] == season) & (stats["week"] == week), "player_id"])
    return upcoming[~upcoming["player_id"].isin(played_now)]


def _prediction_objects(frame: pd.DataFrame, preds: pd.DataFrame, run: ModelRun, backtest: bool) -> list[Prediction]:
    objs = []
    for (_, row), (_, p) in zip(frame.iterrows(), preds.iterrows()):
        objs.append(
            Prediction(
                player_id=row["player_id"],
                model_run=run,
                season=int(row["season"]),
                week=int(row["week"]),
                team=row["team"],
                opponent=row["opponent"],
                is_home=bool(row["is_home"] == 1),
                is_backtest=backtest,
                points_ppr=float(p["ppr"]),
                points_half=float(p["half"]),
                points_std=float(p["std"]),
                recent_avg_ppr=None if pd.isna(row["ppr_last3"]) else round(float(row["ppr_last3"]), 2),
            )
        )
    return objs


def run_pipeline(num_rounds: int | None = None) -> ModelRun:
    kwargs = {"num_rounds": num_rounds} if num_rounds else {}
    stats = stats_frame()
    games = games_frame()
    if stats.empty:
        raise RuntimeError("No stats in the database; run ingest first")

    latest_season = int(stats["season"].max())
    tw = target_week()
    season, week = tw if tw else (latest_season, int(stats.loc[stats["season"] == latest_season, "week"].max()))
    upcoming = upcoming_rows(season, week, stats) if tw else None
    frame = build_features(stats, games, upcoming)

    # 1. Honest accuracy estimate: train on earlier seasons, score the most recent complete season.
    complete_seasons = sorted(s for s in frame["season"].unique() if s < season)
    metrics = evaluate(frame, complete_seasons[-1], **kwargs) if len(complete_seasons) >= 2 else {}

    # 2. Backtest for the current season: a model that never saw this season projects each played week.
    current = frame[(frame["season"] == season) & frame["is_played"].astype(bool)]
    backtest_models = train(frame[frame["season"] < season], **kwargs) if len(complete_seasons) else None

    # 3. Final model on everything played so far, used for the upcoming week.
    final = train(frame[frame["is_played"].astype(bool)], **kwargs)
    last_played = frame[frame["is_played"].astype(bool)].sort_values(["season", "week"]).iloc[-1]

    with transaction.atomic():
        run = ModelRun.objects.create(
            trained_through_season=int(last_played["season"]),
            trained_through_week=int(last_played["week"]),
            training_rows=final.training_rows,
            training_seconds=final.training_seconds,
            features=list(final.boosters["ppr"].feature_name()),
            boosters=final.to_text(),
            metrics={**metrics, "target_season": int(season), "target_week": int(week) if tw else None},
            feature_importance=final.feature_importance(),
        )
        objs = []
        if backtest_models is not None and len(current):
            objs += _prediction_objects(current, backtest_models.predict(current), run, backtest=True)
        if upcoming is not None and len(upcoming):
            to_predict = frame[~frame["is_played"].astype(bool)]
            objs += _prediction_objects(to_predict, final.predict(to_predict), run, backtest=False)
        Prediction.objects.filter(season=season).delete()
        Prediction.objects.bulk_create(objs, batch_size=2000)
        # Keep a few recent runs for comparison; older serialized models are dead weight.
        stale = ModelRun.objects.order_by("-created_at").values_list("pk", flat=True)[KEEP_RUNS:]
        ModelRun.objects.filter(pk__in=list(stale)).delete()
    logger.info(
        "Model run %s: %s training rows in %ss, %s predictions, metrics=%s",
        run.pk, final.training_rows, final.training_seconds, len(objs), metrics,
    )
    return run


def load_latest_models() -> TrainedModels | None:
    run = ModelRun.objects.order_by("-created_at").first()
    return TrainedModels.from_text(run.boosters) if run else None
