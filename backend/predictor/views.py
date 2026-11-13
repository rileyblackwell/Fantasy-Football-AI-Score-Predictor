from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import POSITIONS, InjuryReport, ModelRun, Player, Prediction, RefreshLog, WeeklyStat

SCORING = {"ppr": "points_ppr", "half": "points_half", "std": "points_std"}


def _points(stat: WeeklyStat, scoring: str) -> float:
    if scoring == "ppr":
        return stat.fantasy_points_ppr
    if scoring == "std":
        return stat.fantasy_points_std
    return stat.fantasy_points_half


def _scoring(request) -> str:
    scoring = request.query_params.get("scoring", "ppr")
    return scoring if scoring in SCORING else "ppr"


def _default_week() -> tuple[int, int] | None:
    run = ModelRun.objects.order_by("-created_at").first()
    if run and run.metrics.get("target_week"):
        return run.metrics["target_season"], run.metrics["target_week"]
    latest = Prediction.objects.order_by("-season", "-week").values("season", "week").first()
    return (latest["season"], latest["week"]) if latest else None


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@api_view(["GET"])
def summary(request):
    run = ModelRun.objects.order_by("-created_at").first()
    refresh = RefreshLog.objects.filter(success=True).order_by("-started_at").first()
    default = _default_week()
    weeks = list(Prediction.objects.values("season", "week", "is_backtest").distinct().order_by("-season", "-week"))
    return Response(
        {
            "season": default[0] if default else None,
            "week": default[1] if default else None,
            "weeks": weeks,
            "positions": POSITIONS,
            "last_refreshed": refresh.finished_at if refresh else (run.created_at if run else None),
            "model": None
            if run is None
            else {
                "trained_at": run.created_at,
                "trained_through": {"season": run.trained_through_season, "week": run.trained_through_week},
                "training_rows": run.training_rows,
                "training_seconds": run.training_seconds,
                "metrics": run.metrics,
                "feature_importance": run.feature_importance,
            },
        }
    )


@api_view(["GET"])
def predictions(request):
    default = _default_week()
    if default is None:
        return Response({"season": None, "week": None, "scoring": "ppr", "results": []})
    try:
        season = int(request.query_params.get("season", default[0]))
        week = int(request.query_params.get("week", default[1]))
    except ValueError:
        return Response({"detail": "season and week must be integers"}, status=400)
    scoring = _scoring(request)
    field = SCORING[scoring]

    qs = Prediction.objects.filter(season=season, week=week).select_related("player")
    position = request.query_params.get("position", "").upper()
    if position in POSITIONS:
        qs = qs.filter(player__position=position)
    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(Q(player__name__icontains=search) | Q(team__iexact=search))
    qs = qs.order_by(f"-{field}")

    ids = [p.player_id for p in qs]
    injuries = {
        i.player_id: i for i in InjuryReport.objects.filter(season=season, week=week, player_id__in=ids)
    }
    actuals = {s.player_id: s for s in WeeklyStat.objects.filter(season=season, week=week, player_id__in=ids)}
    results = []
    for rank, p in enumerate(qs, start=1):
        inj = injuries.get(p.player_id)
        actual = actuals.get(p.player_id)
        results.append(
            {
                "rank": rank,
                "player_id": p.player_id,
                "name": p.player.name,
                "position": p.player.position,
                "team": p.team,
                "opponent": p.opponent,
                "is_home": p.is_home,
                "headshot_url": p.player.headshot_url,
                "projected": round(getattr(p, field), 1),
                "recent_avg_ppr": p.recent_avg_ppr,
                "injury_status": inj.status if inj else None,
                "injury": inj.injury if inj else None,
                "actual": round(_points(actual, scoring), 1) if actual else None,
                "is_backtest": p.is_backtest,
            }
        )
    return Response({"season": season, "week": week, "scoring": scoring, "results": results})


@api_view(["GET"])
def player_detail(request, player_id: str):
    try:
        player = Player.objects.get(pk=player_id)
    except Player.DoesNotExist:
        raise Http404("Player not found")
    scoring = _scoring(request)
    field = SCORING[scoring]
    default = _default_week()
    season = int(request.query_params.get("season", default[0] if default else 0))

    stats = {s.week: s for s in WeeklyStat.objects.filter(player=player, season=season)}
    preds = {p.week: p for p in Prediction.objects.filter(player=player, season=season)}
    injuries = {i.week: i for i in InjuryReport.objects.filter(player=player, season=season)}
    weeks = []
    for week in sorted(set(stats) | set(preds)):
        s, p, inj = stats.get(week), preds.get(week), injuries.get(week)
        weeks.append(
            {
                "week": week,
                "opponent": (s.opponent if s else p.opponent),
                "is_home": p.is_home if p else None,
                "actual": round(_points(s, scoring), 1) if s else None,
                "projected": round(getattr(p, field), 1) if p else None,
                "is_backtest": p.is_backtest if p else None,
                "injury_status": inj.status if inj else None,
                "line": None
                if s is None
                else {
                    "pass": f"{s.completions}/{s.attempts}, {s.passing_yards} yds, {s.passing_tds} TD, {s.interceptions} INT",
                    "rush": f"{s.carries} car, {s.rushing_yards} yds, {s.rushing_tds} TD",
                    "rec": f"{s.receptions}/{s.targets}, {s.receiving_yards} yds, {s.receiving_tds} TD",
                },
            }
        )
    season_totals = [w["actual"] for w in weeks if w["actual"] is not None]
    return Response(
        {
            "player_id": player.player_id,
            "name": player.name,
            "position": player.position,
            "team": player.team,
            "headshot_url": player.headshot_url,
            "season": season,
            "scoring": scoring,
            "games_played": len(season_totals),
            "season_avg": round(sum(season_totals) / len(season_totals), 1) if season_totals else None,
            "weeks": weeks,
        }
    )


def spa(request, path: str = ""):
    """Serve the built Vue app for any non-API route so client-side routing works on refresh."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return JsonResponse({"detail": "Frontend not built. Run `npm run build` in frontend/."}, status=404)
    return FileResponse(index.open("rb"), content_type="text/html")
