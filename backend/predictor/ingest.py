"""Download weekly stats, schedules, rosters and injury reports from nflverse and store them.

The cleaning helpers (``clean_*``) are pure pandas functions so they can be unit tested without
network access. ``load_*`` functions download from nflverse; ``store_*`` functions write to the DB.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from django.db import transaction

from .models import DST_PREFIX, POSITIONS, Game, InjuryReport, Player, Team, WeeklyStat

logger = logging.getLogger(__name__)

# nflverse uses current abbreviations in stats, but older schedules still use relocated names.
TEAM_FIXES = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "JAC": "JAX", "WSH": "WAS"}

STAT_COLUMNS = {
    "completions": "completions",
    "attempts": "attempts",
    "passing_yards": "passing_yards",
    "passing_tds": "passing_tds",
    "passing_interceptions": "interceptions",
    "carries": "carries",
    "rushing_yards": "rushing_yards",
    "rushing_tds": "rushing_tds",
    "targets": "targets",
    "receptions": "receptions",
    "receiving_yards": "receiving_yards",
    "receiving_tds": "receiving_tds",
}

DST_COLUMNS = [
    "def_sacks", "def_interceptions", "def_fumble_recoveries", "def_tds", "def_safeties", "def_blocked_kicks",
    "points_allowed",
]

# Ordered from most to least severe, used to keep the worst designation in a week.
INJURY_SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2}


def fix_team(series: pd.Series) -> pd.Series:
    return series.replace(TEAM_FIXES)


def current_season(today: date | None = None) -> int:
    """NFL seasons start in September; January to August belongs to the previous season."""
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1


# --------------------------------------------------------------------------------------------
# Cleaning (pure functions)
# --------------------------------------------------------------------------------------------


def clean_weekly_stats(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep regular-season games for QB/RB/WR/TE and normalize the columns we use."""
    df = raw.copy()
    df = df[df["season_type"] == "REG"]
    df = df[df["player_id"].notna() & df["position"].isin(POSITIONS)]
    df = df[df["team"].notna() & df["opponent_team"].notna()]
    df["team"] = fix_team(df["team"])
    df["opponent"] = fix_team(df["opponent_team"])
    df["name"] = df["player_display_name"].fillna(df.get("player_name")).fillna("Unknown")
    for src, dst in STAT_COLUMNS.items():
        df[dst] = pd.to_numeric(df[src], errors="coerce").fillna(0).round().astype(int)
    df["target_share"] = pd.to_numeric(df["target_share"], errors="coerce")
    df["fantasy_points_ppr"] = pd.to_numeric(df["fantasy_points_ppr"], errors="coerce").fillna(0.0)
    df["fantasy_points_std"] = pd.to_numeric(df["fantasy_points"], errors="coerce").fillna(0.0)
    df["headshot_url"] = df.get("headshot_url", pd.Series(index=df.index, dtype=object)).fillna("")
    # A player can only play once per week; if nflverse ever duplicates a row keep the bigger line.
    df = df.sort_values("fantasy_points_ppr", ascending=False).drop_duplicates(["player_id", "season", "week"])
    for col in DST_COLUMNS:
        df[col] = None if col == "points_allowed" else 0
    return df[STAT_FRAME_COLUMNS].sort_values(["season", "week", "player_id"]).reset_index(drop=True)


STAT_FRAME_COLUMNS = (
    ["player_id", "name", "position", "headshot_url", "season", "week", "team", "opponent"]
    + list(STAT_COLUMNS.values())
    + ["target_share"]
    + DST_COLUMNS
    + ["fantasy_points_std", "fantasy_points_ppr"]
)


def points_allowed_score(points_allowed: float) -> int:
    """Common (ESPN-style) D/ST points-allowed tiers."""
    if points_allowed == 0:
        return 10
    if points_allowed <= 6:
        return 7
    if points_allowed <= 13:
        return 4
    if points_allowed <= 20:
        return 1
    if points_allowed <= 27:
        return 0
    if points_allowed <= 34:
        return -1
    return -4


def dst_fantasy_points(row) -> float:
    return float(
        row["def_sacks"]
        + 2 * row["def_interceptions"]
        + 2 * row["def_fumble_recoveries"]
        + 6 * row["def_tds"]
        + 2 * row["def_safeties"]
        + 2 * row["def_blocked_kicks"]
        + points_allowed_score(row["points_allowed"])
    )


def clean_dst_stats(team_stats: pd.DataFrame, schedule: pd.DataFrame, teams: pd.DataFrame | None = None) -> pd.DataFrame:
    """Turn nflverse team-level weekly stats into one D/ST "player" row per team-game.

    ``schedule`` must already be cleaned; points allowed come from the final score.
    """
    df = team_stats[team_stats["season_type"] == "REG"].copy()
    df["team"] = fix_team(df["team"])
    df["opponent"] = fix_team(df["opponent_team"])

    def num(col):
        return pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df else 0

    df["def_sacks"] = num("def_sacks")
    df["def_interceptions"] = num("def_interceptions").astype(int)
    df["def_fumble_recoveries"] = num("fumble_recovery_opp").astype(int)
    df["def_tds"] = (num("def_tds") + num("special_teams_tds")).astype(int)
    df["def_safeties"] = num("def_safeties").astype(int)
    df["def_blocked_kicks"] = (num("def_punt_blocks") + num("def_fg_blocks")).astype(int)

    scores = pd.concat(
        [
            schedule.rename(columns={"home_team": "team", "away_score": "points_allowed"})[
                ["season", "week", "team", "points_allowed"]
            ],
            schedule.rename(columns={"away_team": "team", "home_score": "points_allowed"})[
                ["season", "week", "team", "points_allowed"]
            ],
        ]
    )
    df = df.merge(scores, on=["season", "week", "team"], how="inner")
    df = df[df["points_allowed"].notna()]
    df["points_allowed"] = df["points_allowed"].astype(int)
    df["fantasy_points_std"] = df.apply(dst_fantasy_points, axis=1)
    df["fantasy_points_ppr"] = df["fantasy_points_std"]

    names = {}
    logos = {}
    if teams is not None and len(teams):
        names = dict(zip(teams["abbr"], teams["name"]))
        logos = dict(zip(teams["abbr"], teams["logo_url"]))
    df["player_id"] = DST_PREFIX + df["team"]
    df["name"] = df["team"].map(lambda t: f"{names.get(t, t)} D/ST")
    df["position"] = "DST"
    df["headshot_url"] = df["team"].map(lambda t: logos.get(t, ""))
    for col in STAT_COLUMNS.values():
        df[col] = 0
    df["target_share"] = None
    df = df.drop_duplicates(["player_id", "season", "week"])
    return df[STAT_FRAME_COLUMNS].sort_values(["season", "week", "player_id"]).reset_index(drop=True)


def clean_teams(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["abbr"] = fix_team(df["team_abbr"])
    # nflverse also lists relocated franchises (STL, SD, OAK); keep the current team's row.
    df["_current"] = df["abbr"] == df["team_abbr"]
    df = df.sort_values("_current").drop_duplicates("abbr", keep="last")
    df = df.rename(
        columns={"team_name": "name", "team_nick": "nickname", "team_color": "color", "team_color2": "color2",
                 "team_logo_espn": "logo_url"}
    )
    return df[["abbr", "name", "nickname", "color", "color2", "logo_url"]].fillna("").reset_index(drop=True)


def clean_schedule(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[raw["game_type"] == "REG"].copy()
    df["home_team"] = fix_team(df["home_team"])
    df["away_team"] = fix_team(df["away_team"])
    df["gameday"] = pd.to_datetime(df["gameday"], errors="coerce").dt.date
    cols = [
        "game_id", "season", "week", "gameday", "home_team", "away_team",
        "home_score", "away_score", "spread_line", "total_line",
    ]
    return df[cols].reset_index(drop=True)


def clean_injuries(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per player-week with the most severe official game status."""
    df = raw[(raw["season_type"] == "REG") & raw["gsis_id"].notna()].copy()
    df = df[df["report_status"].isin(INJURY_SEVERITY)]
    df["severity"] = df["report_status"].map(INJURY_SEVERITY)
    df = df.sort_values("severity").drop_duplicates(["gsis_id", "season", "week"])
    df["injury"] = df["report_primary_injury"].fillna("").astype(str).str.slice(0, 60)
    return df.rename(columns={"gsis_id": "player_id", "report_status": "status"})[
        ["player_id", "season", "week", "status", "injury"]
    ].reset_index(drop=True)


def clean_rosters(raw: pd.DataFrame) -> pd.DataFrame:
    """Latest roster entry per player: current team, status (ACT, RES, ...) and headshot."""
    df = raw[raw["gsis_id"].notna() & raw["position"].isin(POSITIONS)].copy()
    df["team"] = fix_team(df["team"])
    df = df.sort_values("week").drop_duplicates("gsis_id", keep="last")
    return df.rename(columns={"gsis_id": "player_id", "full_name": "name", "status": "roster_status"})[
        ["player_id", "name", "position", "team", "roster_status", "headshot_url", "week"]
    ].reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------------------------


def _nfl():
    import nflreadpy

    return nflreadpy


def load_weekly_stats(seasons: list[int]) -> pd.DataFrame:
    return clean_weekly_stats(_nfl().load_player_stats(seasons, summary_level="week").to_pandas())


def load_teams() -> pd.DataFrame:
    return clean_teams(_nfl().load_teams().to_pandas())


def load_dst_stats(seasons: list[int], schedule: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    raw = _nfl().load_team_stats(seasons, summary_level="week").to_pandas()
    return clean_dst_stats(raw, schedule, teams)


def load_schedule(seasons: list[int]) -> pd.DataFrame:
    return clean_schedule(_nfl().load_schedules(seasons).to_pandas())


def load_injuries(season: int) -> pd.DataFrame:
    try:
        return clean_injuries(_nfl().load_injuries([season]).to_pandas())
    except Exception:  # injury data for a new season can lag behind; predictions still work without it
        logger.warning("Injury data unavailable for %s", season, exc_info=True)
        return pd.DataFrame(columns=["player_id", "season", "week", "status", "injury"])


def load_rosters(season: int) -> pd.DataFrame:
    try:
        return clean_rosters(_nfl().load_rosters_weekly([season]).to_pandas())
    except Exception:
        logger.warning("Weekly rosters unavailable for %s", season, exc_info=True)
        return pd.DataFrame(columns=["player_id", "name", "position", "team", "roster_status", "headshot_url", "week"])


# --------------------------------------------------------------------------------------------
# Storing
# --------------------------------------------------------------------------------------------


def _none_if_nan(value):
    return None if pd.isna(value) else value


@transaction.atomic
def store_weekly_stats(stats: pd.DataFrame, seasons: list[int]) -> int:
    latest = stats.sort_values(["season", "week"]).drop_duplicates("player_id", keep="last")
    players = [
        Player(
            player_id=r.player_id, name=r.name, position=r.position, team=r.team, headshot_url=r.headshot_url or ""
        )
        for r in latest.itertuples()
    ]
    Player.objects.bulk_create(
        players,
        update_conflicts=True,
        unique_fields=["player_id"],
        update_fields=["name", "position", "team", "headshot_url"],
        batch_size=1000,
    )
    WeeklyStat.objects.filter(season__in=seasons).delete()
    rows = [
        WeeklyStat(
            player_id=r.player_id,
            season=r.season,
            week=r.week,
            team=r.team,
            opponent=r.opponent,
            position=r.position,
            target_share=_none_if_nan(r.target_share),
            def_sacks=r.def_sacks,
            def_interceptions=r.def_interceptions,
            def_fumble_recoveries=r.def_fumble_recoveries,
            def_tds=r.def_tds,
            def_safeties=r.def_safeties,
            def_blocked_kicks=r.def_blocked_kicks,
            points_allowed=_none_if_nan(r.points_allowed),
            fantasy_points_std=r.fantasy_points_std,
            fantasy_points_ppr=r.fantasy_points_ppr,
            **{col: getattr(r, col) for col in STAT_COLUMNS.values()},
        )
        for r in stats.itertuples()
    ]
    WeeklyStat.objects.bulk_create(rows, batch_size=2000)
    # Team defenses are always "active".
    Player.objects.filter(position="DST").update(roster_status="ACT")
    return len(rows)


@transaction.atomic
def store_teams(teams: pd.DataFrame) -> int:
    objs = [Team(**row) for row in teams.to_dict("records")]
    Team.objects.bulk_create(
        objs,
        update_conflicts=True,
        unique_fields=["abbr"],
        update_fields=["name", "nickname", "color", "color2", "logo_url"],
    )
    return len(objs)


@transaction.atomic
def store_schedule(schedule: pd.DataFrame) -> int:
    games = [
        Game(
            game_id=r.game_id,
            season=r.season,
            week=r.week,
            gameday=_none_if_nan(r.gameday),
            home_team=r.home_team,
            away_team=r.away_team,
            home_score=_none_if_nan(r.home_score),
            away_score=_none_if_nan(r.away_score),
            spread_line=_none_if_nan(r.spread_line),
            total_line=_none_if_nan(r.total_line),
        )
        for r in schedule.itertuples()
    ]
    Game.objects.bulk_create(
        games,
        update_conflicts=True,
        unique_fields=["game_id"],
        update_fields=["gameday", "home_score", "away_score", "spread_line", "total_line", "home_team", "away_team"],
        batch_size=1000,
    )
    return len(games)


@transaction.atomic
def store_rosters(rosters: pd.DataFrame) -> int:
    """Update team and status for known players, and add rostered players with no stats yet (e.g. rookies)."""
    players = [
        Player(
            player_id=r.player_id,
            name=r.name or "Unknown",
            position=r.position,
            team=r.team or "",
            roster_status=r.roster_status or "",
            headshot_url=r.headshot_url if isinstance(r.headshot_url, str) else "",
        )
        for r in rosters.itertuples()
    ]
    Player.objects.bulk_create(
        players,
        update_conflicts=True,
        unique_fields=["player_id"],
        update_fields=["team", "roster_status", "headshot_url"],
        batch_size=1000,
    )
    return len(players)


@transaction.atomic
def store_injuries(injuries: pd.DataFrame, season: int) -> int:
    known = set(Player.objects.values_list("player_id", flat=True))
    InjuryReport.objects.filter(season=season).delete()
    rows = [
        InjuryReport(player_id=r.player_id, season=r.season, week=r.week, status=r.status, injury=r.injury)
        for r in injuries.itertuples()
        if r.player_id in known
    ]
    InjuryReport.objects.bulk_create(rows, batch_size=2000)
    return len(rows)


def ingest(seasons: list[int]) -> dict:
    """Download and store everything for the given seasons. Rosters/injuries only matter for the latest."""
    latest = max(seasons)
    teams = load_teams()
    store_teams(teams)
    schedule = load_schedule(seasons)
    stats = pd.concat([load_weekly_stats(seasons), load_dst_stats(seasons, schedule, teams)], ignore_index=True)
    n_stats = store_weekly_stats(stats, seasons)
    n_games = store_schedule(schedule)
    n_roster = store_rosters(load_rosters(latest))
    n_inj = store_injuries(load_injuries(latest), latest)
    summary = {"stats": n_stats, "games": n_games, "roster_players": n_roster, "injuries": n_inj}
    logger.info("Ingested seasons %s: %s", seasons, summary)
    return summary
