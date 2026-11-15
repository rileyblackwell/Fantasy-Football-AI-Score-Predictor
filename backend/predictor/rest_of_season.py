"""Rest-of-season projections for the Trade Analyzer.

The model projects one week at a time: the upcoming week. Running it for every later week would need
betting lines and injury reports that don't exist yet, and a full feature build per week. So the rest of
the season is built from what the site already has, at request time, with a handful of small queries:

1. **Per-game rate.** The player's projection for the upcoming week. A player with no game this week (bye)
   uses their most recent projection from earlier this season, and a player ruled Out this week uses that
   earlier projection too, since this week's number is pulled down by the injury. With no projection at
   all, the rate is their season average.
2. **Matchups.** That rate has the upcoming opponent baked in, so it is divided by that opponent's matchup
   factor and multiplied by each later opponent's. A defense's factor is the fantasy points it has allowed
   per game to the position this season, shrunk toward the league average by four average games, then
   damped by half and capped at plus or minus 15%, so one soft or tough defense moves a week by a few
   percent rather than a lot.
3. **Schedule.** The points are summed over the team's unplayed games through the chosen week. A bye week
   has no game, so it adds nothing. The upcoming week uses the model's own projection unchanged (0 if the
   player is ruled Out). Players who aren't on an active roster (injured reserve and the like) get 0.
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Avg, Max, Sum
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import POSITIONS, Game, InjuryReport, Player, Prediction, WeeklyStat
from .views import SCORING, _default_week, _scoring, bye_weeks

# Matchup factor tuning (see the module docstring).
SHRINK_GAMES = 4
DAMPING = 0.5
MAX_SWING = 0.15
MAX_IDS = 20


def matchup_factors(season: int) -> dict[tuple[str, str], float]:
    """(defense team, position) -> multiplier on a player's points against that defense this season."""
    rows = (
        WeeklyStat.objects.filter(season=season)
        .values("opponent", "position", "week")
        .annotate(total=Sum("fantasy_points_ppr"))
    )
    per_defense: dict[tuple[str, str], list[float]] = defaultdict(list)
    per_position: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        per_defense[(r["opponent"], r["position"])].append(r["total"])
        per_position[r["position"]].append(r["total"])
    league = {pos: sum(v) / len(v) for pos, v in per_position.items() if v}
    factors = {}
    for (team, pos), totals in per_defense.items():
        average = league.get(pos, 0)
        if average <= 0:
            continue
        shrunk = (sum(totals) + SHRINK_GAMES * average) / (len(totals) + SHRINK_GAMES)
        damped = 1 + DAMPING * (shrunk / average - 1)
        factors[(team, pos)] = round(min(1 + MAX_SWING, max(1 - MAX_SWING, damped)), 4)
    return factors


def remaining_schedule(season: int, from_week: int, through_week: int) -> dict[str, list[tuple[int, str, bool]]]:
    """Each team's unplayed games from ``from_week`` through ``through_week``: (week, opponent, is_home)."""
    games = Game.objects.filter(
        season=season, week__gte=from_week, week__lte=through_week, home_score__isnull=True
    ).order_by("week")
    schedule: dict[str, list[tuple[int, str, bool]]] = defaultdict(list)
    for g in games:
        schedule[g.home_team].append((g.week, g.away_team, True))
        schedule[g.away_team].append((g.week, g.home_team, False))
    return schedule


def _season_points(row: dict, scoring: str) -> float:
    if scoring == "ppr":
        return row["ppr"]
    if scoring == "std":
        return row["std"]
    return (row["ppr"] + row["std"]) / 2


def project_rest_of_season(
    scoring: str = "ppr", through: int | None = None, ids: list[str] | None = None
) -> dict:
    """Rest-of-season points for every rostered player (or only ``ids``), with week-by-week games."""
    default = _default_week()
    empty = {"season": None, "from_week": None, "through_week": None, "last_week": None, "scoring": scoring, "players": []}
    if default is None or not default[1]:
        return empty
    season, from_week = default
    last_week = Game.objects.filter(season=season).aggregate(w=Max("week"))["w"] or from_week
    through_week = min(max(through or last_week, from_week), last_week)
    field = SCORING[scoring]

    # Anyone who has played this season, plus last season's players who are still on an active roster
    # (rookies and players back from a long injury). Retired and released players are left out.
    has_roster_status = Player.objects.exclude(roster_status="").exists()
    this_season = set(WeeklyStat.objects.filter(season=season).values_list("player_id", flat=True).distinct())
    last_season = set(WeeklyStat.objects.filter(season=season - 1).values_list("player_id", flat=True).distinct())
    players = Player.objects.filter(position__in=POSITIONS, player_id__in=this_season | last_season)
    if ids is not None:
        players = players.filter(player_id__in=ids)
    players = [
        p
        for p in players
        if p.player_id in this_season or not has_roster_status or p.roster_status == "ACT"
    ]
    pids = [p.player_id for p in players]

    now = {p.player_id: p for p in Prediction.objects.filter(season=season, week=from_week, is_backtest=False, player_id__in=pids)}
    earlier = {}
    for p in Prediction.objects.filter(
        season=season, week__lt=from_week, is_backtest=False, player_id__in=pids
    ).order_by("week"):
        earlier[p.player_id] = p  # the latest week wins
    averages = {
        r["player_id"]: r
        for r in WeeklyStat.objects.filter(season=season, player_id__in=pids)
        .values("player_id")
        .annotate(ppr=Avg("fantasy_points_ppr"), std=Avg("fantasy_points_std"))
    }
    injuries = {
        i.player_id: i.status
        for i in InjuryReport.objects.filter(season=season, week=from_week, player_id__in=pids)
    }
    factors = matchup_factors(season)
    schedule = remaining_schedule(season, from_week, through_week)
    byes = bye_weeks(season)

    def factor(team: str, pos: str) -> float:
        return factors.get((team, pos), 1.0)

    results = []
    for player in players:
        pos, team = player.position, player.team
        status = injuries.get(player.player_id)
        out = status == "Out"
        current, previous = now.get(player.player_id), earlier.get(player.player_id)
        active = not has_roster_status or player.roster_status == "ACT"

        if not active:
            rate, basis = 0.0, "inactive"
        elif current is not None and not out:
            rate, basis = getattr(current, field) / factor(current.opponent, pos), "projection"
        elif previous is not None:
            rate, basis = getattr(previous, field) / factor(previous.opponent, pos), "recent_projection"
        elif player.player_id in averages:
            rate, basis = _season_points(averages[player.player_id], scoring), "season_avg"
        else:
            rate, basis = 0.0, "none"

        games = []
        for week, opponent, is_home in schedule.get(team, []):
            if not active:
                pts = 0.0
            elif week == from_week and out:
                pts = 0.0
            elif week == from_week and current is not None:
                pts = getattr(current, field)
            else:
                pts = rate * factor(opponent, pos)
            games.append({"week": week, "opponent": opponent, "is_home": is_home, "points": pts})

        bye = byes.get(team)
        results.append(
            {
                "player_id": player.player_id,
                "name": player.name,
                "position": pos,
                "team": team,
                "headshot_url": player.headshot_url,
                "injury_status": status,
                "roster_status": player.roster_status,
                "basis": basis,
                "per_game": round(rate, 1),
                "games_left": len(games),
                "bye_week": bye if bye and from_week <= bye <= through_week else None,
                "total": round(sum(g["points"] for g in games), 1),
                "games": [{**g, "points": round(g["points"], 1)} for g in games],
            }
        )
    results.sort(key=lambda r: -r["total"])
    return {
        "season": season,
        "from_week": from_week,
        "through_week": through_week,
        "last_week": last_week,
        "scoring": scoring,
        "players": results,
    }


@api_view(["GET"])
def rest_of_season(request):
    """Rest-of-season projections. Without ``ids``, every player with totals only (for the picker);
    with ``ids=a,b``, just those players including their week-by-week games."""
    try:
        through = int(request.query_params["through"]) if request.query_params.get("through") else None
    except ValueError:
        return Response({"detail": "through must be an integer"}, status=400)
    raw_ids = request.query_params.get("ids")
    ids = [i for i in (raw_ids or "").split(",") if i][:MAX_IDS] if raw_ids is not None else None
    data = project_rest_of_season(_scoring(request), through, ids)
    if ids is None:
        for row in data["players"]:
            del row["games"]
    return Response(data)
