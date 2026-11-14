from django.db import models

POSITIONS = ("QB", "RB", "WR", "TE", "DST")
DST_PREFIX = "DST-"
SCORING_FORMATS = ("ppr", "half", "std")


class Team(models.Model):
    """An NFL team, with colors and logo for the UI."""

    abbr = models.CharField(max_length=4, primary_key=True)
    name = models.CharField(max_length=60)
    nickname = models.CharField(max_length=40)
    color = models.CharField(max_length=9, blank=True)
    color2 = models.CharField(max_length=9, blank=True)
    logo_url = models.URLField(max_length=300, blank=True)

    def __str__(self) -> str:
        return self.name


class Player(models.Model):
    """An NFL skill-position player, keyed by the nflverse GSIS id (e.g. 00-0033873).

    Team defenses are players too, with ids like ``DST-KC`` and position ``DST``.
    """

    player_id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=4, db_index=True)
    team = models.CharField(max_length=4, blank=True, db_index=True)
    headshot_url = models.URLField(max_length=300, blank=True)
    roster_status = models.CharField(max_length=10, blank=True)
    # Career context for the model (empty for team defenses and players nflverse has no bio for).
    birth_date = models.DateField(null=True, blank=True)
    rookie_season = models.PositiveSmallIntegerField(null=True, blank=True)
    draft_pick = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.position}, {self.team})"


class Game(models.Model):
    """One regular-season game from the nflverse schedule, with betting lines."""

    game_id = models.CharField(max_length=20, primary_key=True)
    season = models.PositiveSmallIntegerField()
    week = models.PositiveSmallIntegerField()
    gameday = models.DateField(null=True)
    home_team = models.CharField(max_length=4)
    away_team = models.CharField(max_length=4)
    home_score = models.SmallIntegerField(null=True)
    away_score = models.SmallIntegerField(null=True)
    spread_line = models.FloatField(null=True, help_text="Home team spread; positive means home is favored.")
    total_line = models.FloatField(null=True)

    class Meta:
        indexes = [models.Index(fields=["season", "week"])]

    @property
    def is_final(self) -> bool:
        return self.home_score is not None


class WeeklyStat(models.Model):
    """A player's box score and fantasy points for one regular-season game."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="stats")
    season = models.PositiveSmallIntegerField()
    week = models.PositiveSmallIntegerField()
    team = models.CharField(max_length=4)
    opponent = models.CharField(max_length=4)
    position = models.CharField(max_length=4)
    completions = models.SmallIntegerField(default=0)
    attempts = models.SmallIntegerField(default=0)
    passing_yards = models.SmallIntegerField(default=0)
    passing_tds = models.SmallIntegerField(default=0)
    interceptions = models.SmallIntegerField(default=0)
    carries = models.SmallIntegerField(default=0)
    rushing_yards = models.SmallIntegerField(default=0)
    rushing_tds = models.SmallIntegerField(default=0)
    targets = models.SmallIntegerField(default=0)
    receptions = models.SmallIntegerField(default=0)
    receiving_yards = models.SmallIntegerField(default=0)
    receiving_tds = models.SmallIntegerField(default=0)
    target_share = models.FloatField(null=True)
    # Usage detail for the model: share of the team's offensive snaps (0-1), expected PPR points from
    # the volume and location of the player's looks, and air yards on targets.
    offense_snap_pct = models.FloatField(null=True)
    expected_ppr = models.FloatField(null=True)
    air_yards = models.FloatField(null=True)
    # Team defense / special teams (only set for DST rows)
    def_sacks = models.FloatField(default=0)
    def_interceptions = models.SmallIntegerField(default=0)
    def_fumble_recoveries = models.SmallIntegerField(default=0)
    def_tds = models.SmallIntegerField(default=0)
    def_safeties = models.SmallIntegerField(default=0)
    def_blocked_kicks = models.SmallIntegerField(default=0)
    points_allowed = models.SmallIntegerField(null=True)
    fantasy_points_std = models.FloatField()
    fantasy_points_ppr = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "season", "week"], name="uniq_player_week")]
        indexes = [models.Index(fields=["season", "week"])]

    @property
    def fantasy_points_half(self) -> float:
        return round((self.fantasy_points_std + self.fantasy_points_ppr) / 2, 2)


class InjuryReport(models.Model):
    """Official game-status designation (Out, Doubtful, Questionable) for a player in a week."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="injuries")
    season = models.PositiveSmallIntegerField()
    week = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20)
    injury = models.CharField(max_length=60, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "season", "week"], name="uniq_injury_week")]


class ModelRun(models.Model):
    """A trained LightGBM model. The serialized boosters live in the database so they survive redeploys."""

    created_at = models.DateTimeField(auto_now_add=True)
    trained_through_season = models.PositiveSmallIntegerField()
    trained_through_week = models.PositiveSmallIntegerField()
    training_rows = models.PositiveIntegerField()
    training_seconds = models.FloatField()
    features = models.JSONField()
    boosters = models.JSONField(help_text="Map of scoring format to LightGBM model text.")
    metrics = models.JSONField(default=dict)
    feature_importance = models.JSONField(default=list)

    class Meta:
        get_latest_by = "created_at"


class Prediction(models.Model):
    """A projected fantasy score for one player in one week."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="predictions")
    model_run = models.ForeignKey(ModelRun, on_delete=models.SET_NULL, null=True, related_name="predictions")
    season = models.PositiveSmallIntegerField()
    week = models.PositiveSmallIntegerField()
    team = models.CharField(max_length=4)
    opponent = models.CharField(max_length=4)
    is_home = models.BooleanField()
    is_backtest = models.BooleanField(
        default=False, help_text="Made for an already-played week by a model trained only on earlier seasons."
    )
    points_ppr = models.FloatField()
    points_half = models.FloatField()
    points_std = models.FloatField()
    recent_avg_ppr = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "season", "week"], name="uniq_prediction_week")]
        indexes = [models.Index(fields=["season", "week"])]


class RefreshLog(models.Model):
    """One run of the scheduled refresh job."""

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    success = models.BooleanField(default=False)
    message = models.TextField(blank=True)
