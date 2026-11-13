from django.contrib import admin

from .models import Game, InjuryReport, ModelRun, Player, Prediction, RefreshLog, WeeklyStat


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "team", "roster_status")
    list_filter = ("position", "roster_status")
    search_fields = ("name", "player_id")


@admin.register(WeeklyStat)
class WeeklyStatAdmin(admin.ModelAdmin):
    list_display = ("player", "season", "week", "team", "opponent", "fantasy_points_ppr")
    list_filter = ("season", "position")
    search_fields = ("player__name",)
    raw_id_fields = ("player",)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("player", "season", "week", "opponent", "points_ppr", "is_backtest")
    list_filter = ("season", "week", "is_backtest")
    search_fields = ("player__name",)
    raw_id_fields = ("player", "model_run")


@admin.register(ModelRun)
class ModelRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "trained_through_season", "trained_through_week", "training_rows", "training_seconds")
    exclude = ("boosters",)


@admin.register(RefreshLog)
class RefreshLogAdmin(admin.ModelAdmin):
    list_display = ("started_at", "finished_at", "success")


admin.site.register(Game)
admin.site.register(InjuryReport)
