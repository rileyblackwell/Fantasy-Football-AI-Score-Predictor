"""Waiver wire helper: skill players whose share of the offense is climbing.

A player is flagged when their average snap share or target share over their last few games is clearly
higher than it was in their earlier games this season. Rising usage tends to show up in the box score a
week or two before the fantasy points do, which is when the player is still cheap to pick up.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import InjuryReport, Prediction, WeeklyStat
from .views import SCORING, _default_week, _points, _scoring

WAIVER_POSITIONS = ("QB", "RB", "WR", "TE")
RECENT_GAMES = 3  # games in the "now" window
MIN_PRIOR_GAMES = 2  # earlier games needed to compare against
STALE_AFTER_WEEKS = 1  # last game must be in the latest completed week or the one before
SNAP_RISE = 0.10  # +10 points of snap share
TARGET_RISE = 0.05  # +5 points of target share
MIN_RECENT_SNAPS = 0.40  # a rise from 5% to 15% of snaps is noise, not a role
MIN_RECENT_TARGETS = 0.12
HISTORY_GAMES = 8  # weekly points returned for the trend chart


def _avg(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _change(recent: float | None, prior: float | None) -> float | None:
    return None if recent is None or prior is None else recent - prior


def usage_trend(games: list[dict], position: str, through_week: int) -> dict | None:
    """Compare a player's recent usage with their earlier games this season.

    ``games`` are one player's rows for the season (dicts with ``week``, ``offense_snap_pct`` and
    ``target_share``), in any order. Returns the trend if snaps or targets are rising, else None.
    """
    games = sorted(games, key=lambda g: g["week"])
    if len(games) < RECENT_GAMES + MIN_PRIOR_GAMES:
        return None
    # Someone who hasn't played lately (injured, benched, cut) has no current role to chase.
    if games[-1]["week"] < through_week - STALE_AFTER_WEEKS:
        return None
    recent, prior = games[-RECENT_GAMES:], games[:-RECENT_GAMES]

    snap_recent = _avg(g["offense_snap_pct"] for g in recent)
    snap_prior = _avg(g["offense_snap_pct"] for g in prior)
    snap_change = _change(snap_recent, snap_prior)
    # Target share means nothing for a quarterback.
    if position == "QB":
        target_recent = target_prior = target_change = None
    else:
        target_recent = _avg(g["target_share"] for g in recent)
        target_prior = _avg(g["target_share"] for g in prior)
        target_change = _change(target_recent, target_prior)

    rising_snaps = snap_change is not None and snap_change >= SNAP_RISE and snap_recent >= MIN_RECENT_SNAPS
    rising_targets = (
        target_change is not None and target_change >= TARGET_RISE and target_recent >= MIN_RECENT_TARGETS
    )
    if not (rising_snaps or rising_targets):
        return None
    # Targets count double: a target is worth far more to a fantasy score than a snap.
    score = (snap_change if rising_snaps else 0) + 2 * (target_change if rising_targets else 0)

    def pct(value):
        return None if value is None else round(value, 3)

    return {
        "rising_snaps": rising_snaps,
        "rising_targets": rising_targets,
        "trend_score": round(score, 3),
        "snap_share": {"recent": pct(snap_recent), "prior": pct(snap_prior), "change": pct(snap_change)},
        "target_share": {"recent": pct(target_recent), "prior": pct(target_prior), "change": pct(target_change)},
        "games_recent": len(recent),
        "games_prior": len(prior),
    }


@api_view(["GET"])
def waivers(request):
    """Players whose usage is climbing, with this week's projection and injury status."""
    scoring = _scoring(request)
    default = _default_week()
    empty = {"season": None, "week": None, "through_week": None, "scoring": scoring, "results": []}
    if default is None:
        return Response(empty)
    try:
        season = int(request.query_params.get("season", default[0]))
        week = int(request.query_params.get("week", default[1]))
    except ValueError:
        return Response({"detail": "season and week must be integers"}, status=400)
    positions = WAIVER_POSITIONS
    position = request.query_params.get("position", "").upper()
    if position in WAIVER_POSITIONS:
        positions = (position,)

    stats = WeeklyStat.objects.filter(season=season, week__lt=week, position__in=positions).select_related("player")
    by_player: dict[str, list[WeeklyStat]] = {}
    for s in stats:
        by_player.setdefault(s.player_id, []).append(s)
    through_week = max((s.week for rows in by_player.values() for s in rows), default=None)
    if through_week is None:
        return Response({**empty, "season": season, "week": week})

    field = SCORING[scoring]
    preds = Prediction.objects.filter(season=season, week=week, player__position__in=WAIVER_POSITIONS)
    preds = list(preds.select_related("player").order_by(f"-{field}"))
    projections = {p.player_id: p for p in preds}
    # Positional rank by projection, so the page can hide players who are already every-week starters.
    position_rank, counters = {}, {}
    for p in preds:
        pos = p.player.position
        counters[pos] = counters.get(pos, 0) + 1
        position_rank[p.player_id] = counters[pos]

    flagged = []
    for player_id, rows in by_player.items():
        rows.sort(key=lambda s: s.week)
        player = rows[-1].player
        games = [{"week": s.week, "offense_snap_pct": s.offense_snap_pct, "target_share": s.target_share} for s in rows]
        trend = usage_trend(games, player.position, through_week)
        if trend is None:
            continue
        recent_points = [_points(s, scoring) for s in rows[-RECENT_GAMES:]]
        prior_points = [_points(s, scoring) for s in rows[:-RECENT_GAMES]]
        flagged.append((player, rows, trend, recent_points, prior_points))

    ids = [player.player_id for player, *_ in flagged]
    # Players with no projection this week (on bye, or dropped from the slate) would otherwise have no
    # rank and slip past the "likely starter" filter. Slot their latest projection into this week's ranks.
    rank_week = {}
    missing = [pid for pid in ids if pid not in projections]
    latest = Prediction.objects.filter(season=season, week__lt=week, player_id__in=missing).order_by("player_id", "-week")
    week_values: dict[str, list[float]] = {}
    for p in preds:
        week_values.setdefault(p.player.position, []).append(getattr(p, field))
    positions_by_id = {player.player_id: player.position for player, *_ in flagged}
    for p in latest:
        if p.player_id in rank_week:
            continue  # already took this player's most recent week
        value = getattr(p, field)
        others = week_values.get(positions_by_id[p.player_id], [])
        position_rank[p.player_id] = 1 + sum(v > value for v in others)
        rank_week[p.player_id] = p.week

    injuries = {i.player_id: i for i in InjuryReport.objects.filter(season=season, week=week, player_id__in=ids)}
    results = []
    for player, rows, trend, recent_points, prior_points in flagged:
        pred, inj = projections.get(player.player_id), injuries.get(player.player_id)
        results.append(
            {
                "player_id": player.player_id,
                "name": player.name,
                "position": player.position,
                "team": pred.team if pred else rows[-1].team,
                "opponent": pred.opponent if pred else None,
                "is_home": pred.is_home if pred else None,
                "headshot_url": player.headshot_url,
                "projected": round(getattr(pred, field), 1) if pred else None,
                "position_rank": position_rank.get(player.player_id),
                # Set when the rank comes from an earlier week's projection rather than this week's.
                "rank_from_week": rank_week.get(player.player_id),
                "injury_status": inj.status if inj else None,
                "injury": inj.injury if inj else None,
                "points_recent": round(sum(recent_points) / len(recent_points), 1),
                "points_prior": round(sum(prior_points) / len(prior_points), 1),
                "history": [
                    {"week": s.week, "snap_share": s.offense_snap_pct, "target_share": s.target_share}
                    for s in rows[-HISTORY_GAMES:]
                ],
                **trend,
            }
        )
    results.sort(key=lambda r: (-r["trend_score"], -(r["projected"] or 0)))
    return Response(
        {"season": season, "week": week, "through_week": through_week, "scoring": scoring, "results": results}
    )
