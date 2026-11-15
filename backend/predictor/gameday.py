"""Game-day injury refresh.

The daily refresh retrains the model once a morning. On game days a player listed Questionable is
often ruled Out shortly before kickoff (teams name their inactives 90 minutes before), so between
those daily runs this job pulls the latest game statuses during the hours around each kickoff and
re-projects the players whose games haven't started yet. It never retrains, so it stays cheap.

Statuses come from ESPN's public injury feed, which teams' late calls reach within minutes. nflverse
rebuilds its injury file only once a day (about 2am ET), so it is the fallback when ESPN can't be
read: the job then keeps the official report the daily refresh loaded.

The window follows the schedule, so each game day gets its own hours:

* Sunday: from 5 hours before the first kickoff until 1 hour after the last one.
* Thursday and Monday nights: the same rule around the night game, so only the evening.
* Any other day with a game (a late-season Saturday, a holiday) is covered the same way.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from django.db import transaction
from django.utils import timezone

from .features import FEATURES, build_features
from .ingest import load_injuries, load_schedule, store_schedule
from .models import Game, InjuryReport, ModelRun, Player, Prediction
from .pipeline import (
    _prediction_objects,
    games_frame,
    injuries_frame,
    load_latest_models,
    players_frame,
    stats_frame,
    target_week,
    upcoming_rows,
)

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")
OPEN_BEFORE_KICKOFF = timedelta(hours=5)
CLOSE_AFTER_KICKOFF = timedelta(hours=1)


def game_windows(kickoffs: list[datetime]) -> list[tuple[datetime, datetime]]:
    """One (start, end) window per calendar day (Eastern time) that has games."""
    by_day: dict = {}
    for k in kickoffs:
        by_day.setdefault(timezone.localtime(k, EASTERN).date(), []).append(k)
    return sorted(
        (min(ks) - OPEN_BEFORE_KICKOFF, max(ks) + CLOSE_AFTER_KICKOFF) for ks in by_day.values()
    )


def in_game_window(now: datetime, kickoffs: list[datetime]) -> bool:
    return any(start <= now <= end for start, end in game_windows(kickoffs))


def _week_kickoffs(season: int, week: int) -> list[datetime]:
    return list(
        Game.objects.filter(season=season, week=week, kickoff__isnull=False).values_list("kickoff", flat=True)
    )


def ensure_kickoffs(season: int, week: int) -> list[datetime]:
    """Kickoff times for the week, loading the schedule once if they were never stored."""
    kickoffs = _week_kickoffs(season, week)
    if not kickoffs:
        store_schedule(load_schedule([season]))
        kickoffs = _week_kickoffs(season, week)
    return kickoffs


ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
ESPN_TIMEOUT_SECONDS = 20
# ESPN's statuses mapped to the official game designations the model knows. Anyone on a reserve
# list or suspended won't play this week, so they count as Out.
ESPN_STATUS = {
    "Out": "Out",
    "Doubtful": "Doubtful",
    "Questionable": "Questionable",
    "Injured Reserve": "Out",
    "Physically Unable to Perform": "Out",
    "Non-Football Injury": "Out",
    "Suspension": "Out",
}
SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2}
# A response with injuries for fewer teams than this is treated as broken and not used.
ESPN_MIN_TEAMS = 16
STATUS_COLUMNS = ["player_id", "season", "week", "status", "injury"]
_ESPN_ID_PATTERNS = [re.compile(r"/athletes/(\d+)/"), re.compile(r"/id/(\d+)"), re.compile(r"/(\d+)\.png")]


def espn_athlete_id(athlete: dict) -> str | None:
    """ESPN's numeric athlete id. The feed has no id field on the athlete, so read it from the
    injury note's reference, the player page links or the headshot file name."""
    if athlete.get("id"):
        return str(athlete["id"])
    texts = [i.get("injury", {}).get("$ref", "") for i in athlete.get("notes", {}).get("items", [])]
    texts += [link.get("href", "") for link in athlete.get("links", [])]
    texts.append(athlete.get("headshot", {}).get("href", ""))
    for pattern in _ESPN_ID_PATTERNS:
        for text in texts:
            match = pattern.search(text or "")
            if match:
                return match.group(1)
    return None


def parse_espn_injuries(payload: dict, espn_to_player: dict[str, str], season: int, week: int) -> pd.DataFrame | None:
    """Our players' statuses from ESPN's league-wide injury feed, or None if the response looks broken."""
    teams = payload.get("injuries") if isinstance(payload, dict) else None
    if not isinstance(teams, list) or len(teams) < ESPN_MIN_TEAMS:
        return None
    rows = []
    for team in teams:
        for item in team.get("injuries") or []:
            status = ESPN_STATUS.get(item.get("status"))
            player_id = espn_to_player.get(espn_athlete_id(item.get("athlete") or {}) or "")
            if status and player_id:
                injury = ((item.get("details") or {}).get("type") or "")[:60]
                rows.append({"player_id": player_id, "season": season, "week": week, "status": status, "injury": injury})
    df = pd.DataFrame(rows, columns=STATUS_COLUMNS)
    df = df.assign(severity=df["status"].map(SEVERITY)).sort_values("severity").drop_duplicates("player_id")
    return df[STATUS_COLUMNS].reset_index(drop=True)


def load_espn_injuries(season: int, week: int) -> pd.DataFrame | None:
    """Download and parse ESPN's feed; None when it can't be read or matched to our players."""
    espn_to_player = dict(Player.objects.exclude(espn_id="").values_list("espn_id", "player_id"))
    if not espn_to_player:  # filled by the daily refresh from the nflverse players table
        logger.warning("No ESPN ids stored yet; skipping ESPN's injury feed")
        return None
    request = urllib.request.Request(ESPN_INJURIES_URL, headers={"User-Agent": "fantasy-score-predictor"})
    try:
        with urllib.request.urlopen(request, timeout=ESPN_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except Exception:
        logger.warning("ESPN injury feed unavailable", exc_info=True)
        return None
    parsed = parse_espn_injuries(payload, espn_to_player, season, week)
    if parsed is None:
        logger.warning("ESPN injury feed looked incomplete; not using it")
    return parsed


def fetch_statuses(season: int, week: int) -> tuple[pd.DataFrame, str]:
    """Latest game statuses for the week and where they came from ("espn" or "nflverse")."""
    espn = load_espn_injuries(season, week)
    if espn is not None:
        return espn, "espn"
    injuries = load_injuries([season])
    return injuries[injuries["week"] == week], "nflverse"


@transaction.atomic
def apply_statuses(fresh: pd.DataFrame, season: int, week: int) -> set[str]:
    """Replace the week's injury report with ``fresh`` and return the players whose status changed."""
    known = set(Player.objects.values_list("player_id", flat=True))
    fresh = fresh[fresh["player_id"].isin(known)].drop_duplicates("player_id")
    before = dict(InjuryReport.objects.filter(season=season, week=week).values_list("player_id", "status"))
    after = dict(zip(fresh["player_id"], fresh["status"]))
    changed = {pid for pid in before.keys() | after.keys() if before.get(pid) != after.get(pid)}
    if changed:
        InjuryReport.objects.filter(season=season, week=week).delete()
        InjuryReport.objects.bulk_create(
            [
                InjuryReport(player_id=r.player_id, season=season, week=week, status=r.status, injury=r.injury)
                for r in fresh.itertuples()
            ]
        )
    return changed


def started_teams(season: int, week: int, now: datetime) -> set[str]:
    """Teams whose game this week has kicked off or finished: their published projections stand."""
    teams = set()
    for g in Game.objects.filter(season=season, week=week):
        if g.home_score is not None or (g.kickoff is not None and g.kickoff <= now):
            teams |= {g.home_team, g.away_team}
    return teams


def reproject(season: int, week: int, now: datetime) -> int:
    """Re-score this week's players whose game hasn't started, with the latest model and the current
    injury report. Teammates of a player ruled Out pick up his workload through the injury features."""
    run = ModelRun.objects.order_by("-created_at").first()
    models = load_latest_models()
    if run is None or models is None:
        return 0
    if list(run.features or []) != list(FEATURES):
        logger.warning("Latest model was trained on other features; waiting for the daily retrain")
        return 0
    stats = stats_frame()
    upcoming = upcoming_rows(season, week, stats)
    upcoming = upcoming[~upcoming["team"].isin(started_teams(season, week, now))]
    if upcoming.empty:
        return 0
    frame = build_features(stats, games_frame(), upcoming, players=players_frame(), injuries=injuries_frame())
    target = frame[
        ~frame["is_played"].astype(bool)
        & (frame["season"] == season)
        & (frame["week"] == week)
        & frame["player_id"].isin(set(upcoming["player_id"]))
    ]
    if target.empty:
        return 0
    objs = _prediction_objects(target, models.predict(target), run, backtest=False)
    with transaction.atomic():
        Prediction.objects.filter(
            season=season, week=week, is_backtest=False, player_id__in=list(target["player_id"])
        ).delete()
        Prediction.objects.bulk_create(objs, batch_size=2000)
    return len(objs)


def refresh_game_day(now: datetime | None = None, force: bool = False) -> dict:
    """Run one game-day check. Returns a summary; ``ran`` is False outside a game window."""
    now = now or timezone.now()
    tw = target_week()
    if tw is None:
        return {"ran": False, "reason": "season is over"}
    season, week = tw
    if not force and not in_game_window(now, ensure_kickoffs(season, week)):
        return {"ran": False, "reason": "no game window right now"}
    fresh, source = fetch_statuses(season, week)
    if fresh.empty:  # a failed download returns nothing; keep the report we have
        return {"ran": True, "season": season, "week": week, "source": source, "changed": [], "newly_out": [],
                "reprojected": 0}
    before_out = set(
        InjuryReport.objects.filter(season=season, week=week, status="Out").values_list("player_id", flat=True)
    )
    changed = apply_statuses(fresh, season, week)
    now_out = set(
        InjuryReport.objects.filter(season=season, week=week, status="Out").values_list("player_id", flat=True)
    )
    reprojected = reproject(season, week, now) if changed else 0
    return {
        "ran": True,
        "season": season,
        "week": week,
        "source": source,
        "changed": sorted(changed),
        "newly_out": sorted(now_out - before_out),
        "reprojected": reprojected,
    }

