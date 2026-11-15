from datetime import datetime, timedelta
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

import pandas as pd
from django.core.management import call_command
from django.test import TestCase

from predictor.gameday import game_windows, in_game_window, refresh_game_day
from predictor.ingest import clean_schedule, kickoff_times
from predictor.models import Game, InjuryReport, Prediction, RefreshLog
from predictor.pipeline import run_pipeline
from predictor.tests.factories import populate_db

ET = ZoneInfo("America/New_York")


def et(*args):
    return datetime(*args, tzinfo=ET)


# Week 11 of 2026: Thursday night, a full Sunday slate, Monday night.
THU = et(2026, 11, 12, 20, 15)
SUNDAY = [et(2026, 11, 15, 13, 0), et(2026, 11, 15, 16, 25), et(2026, 11, 15, 20, 20)]
MON = et(2026, 11, 16, 20, 15)
WEEK = [THU, *SUNDAY, MON]


def statuses(rows):
    return pd.DataFrame(
        [{"player_id": p, "season": 2025, "week": 4, "status": s, "injury": "Knee"} for p, s in rows],
        columns=["player_id", "season", "week", "status", "injury"],
    )


class KickoffTimeTests(TestCase):
    def test_eastern_game_time_becomes_utc(self):
        raw = pd.DataFrame({"gameday": ["2026-11-15", "2026-09-13", None], "gametime": ["13:00", "20:20", None]})
        kick = kickoff_times(raw)
        self.assertEqual(kick[0], pd.Timestamp("2026-11-15 18:00", tz="UTC"))  # EST, UTC-5
        self.assertEqual(kick[1], pd.Timestamp("2026-09-14 00:20", tz="UTC"))  # EDT, UTC-4
        self.assertTrue(pd.isna(kick[2]))

    def test_clean_schedule_keeps_kickoff(self):
        raw = pd.DataFrame(
            [{"game_id": "g", "season": 2026, "week": 11, "game_type": "REG", "gameday": "2026-11-16",
              "gametime": "20:15", "home_team": "LV", "away_team": "DAL", "home_score": None, "away_score": None,
              "spread_line": 3.0, "total_line": 45.0}]
        )
        self.assertEqual(clean_schedule(raw).loc[0, "kickoff"], pd.Timestamp("2026-11-17 01:15", tz="UTC"))


class GameWindowTests(TestCase):
    def test_each_game_day_gets_its_own_window(self):
        windows = [(a.astimezone(ET), b.astimezone(ET)) for a, b in game_windows(WEEK)]
        self.assertEqual(
            windows,
            [
                (et(2026, 11, 12, 15, 15), et(2026, 11, 12, 21, 15)),  # Thursday evening only
                (et(2026, 11, 15, 8, 0), et(2026, 11, 15, 21, 20)),  # Sunday, first kickoff to the night game
                (et(2026, 11, 16, 15, 15), et(2026, 11, 16, 21, 15)),  # Monday evening only
            ],
        )

    def test_hours_inside_and_outside_the_windows(self):
        inside = [et(2026, 11, 12, 19, 0), et(2026, 11, 15, 8, 0), et(2026, 11, 15, 12, 0),
                  et(2026, 11, 15, 19, 0), et(2026, 11, 16, 18, 0)]
        outside = [et(2026, 11, 12, 12, 0), et(2026, 11, 13, 10, 0), et(2026, 11, 14, 19, 0),
                   et(2026, 11, 15, 7, 0), et(2026, 11, 15, 22, 0), et(2026, 11, 16, 13, 0)]
        for now in inside:
            self.assertTrue(in_game_window(now, WEEK), now)
        for now in outside:
            self.assertFalse(in_game_window(now, WEEK), now)


class GameDayRefreshTests(TestCase):
    """Synthetic league: 2025 week 4 is next, AAA-BBB and CCC-DDD play at 1pm and 4:25pm ET."""

    def setUp(self):
        populate_db()
        run_pipeline(num_rounds=10)
        Game.objects.filter(season=2025, week=4, home_team="AAA").update(kickoff=et(2025, 9, 28, 13, 0))
        Game.objects.filter(season=2025, week=4, home_team="CCC").update(kickoff=et(2025, 9, 28, 16, 25))
        InjuryReport.objects.create(player_id="00-DDD-WR", season=2025, week=4, status="Questionable", injury="Knee")

    def run_at(self, now, rows):
        with mock.patch("predictor.gameday.fetch_statuses", return_value=statuses(rows)) as fetch:
            return refresh_game_day(now=now), fetch

    def test_outside_the_window_nothing_is_downloaded(self):
        summary, fetch = self.run_at(et(2025, 9, 27, 12, 0), [])
        self.assertFalse(summary["ran"])
        fetch.assert_not_called()

    def test_player_ruled_out_shows_out_and_is_reprojected(self):
        before = {p.player_id: p.points_ppr for p in Prediction.objects.filter(season=2025, week=4)}
        # 3pm ET: the 1pm game has started, the 4:25pm game hasn't.
        summary, _ = self.run_at(et(2025, 9, 28, 15, 0), [("00-DDD-WR", "Out"), ("00-AAA-RB", "Out")])

        self.assertTrue(summary["ran"])
        self.assertEqual(summary["newly_out"], ["00-AAA-RB", "00-DDD-WR"])
        self.assertEqual(InjuryReport.objects.get(player_id="00-DDD-WR", week=4).status, "Out")
        # Only the 4:25pm game's 10 players are re-projected; the 1pm game's projections stand.
        self.assertEqual(summary["reprojected"], 10)
        after = {p.player_id: p.points_ppr for p in Prediction.objects.filter(season=2025, week=4)}
        self.assertEqual(set(after), set(before))
        for team in ["AAA", "BBB"]:
            for pos in ["QB", "RB", "WR", "TE"]:
                self.assertEqual(after[f"00-{team}-{pos}"], before[f"00-{team}-{pos}"])
        self.assertFalse(Prediction.objects.filter(season=2025, week=4, is_backtest=True).exists())

        # The projections, Start/Sit and player pages all read the week's report.
        rows = {r["player_id"]: r for r in self.client.get("/api/predictions?season=2025&week=4").json()["results"]}
        self.assertEqual(rows["00-DDD-WR"]["injury_status"], "Out")
        self.assertEqual(rows["00-AAA-RB"]["injury_status"], "Out")

    def test_no_change_means_no_reprojection(self):
        summary, _ = self.run_at(et(2025, 9, 28, 11, 0), [("00-DDD-WR", "Questionable")])
        self.assertEqual(summary["changed"], [])
        self.assertEqual(summary["reprojected"], 0)

    def test_a_failed_download_keeps_the_current_report(self):
        summary, _ = self.run_at(et(2025, 9, 28, 11, 0), [])
        self.assertTrue(summary["ran"])
        self.assertTrue(InjuryReport.objects.filter(player_id="00-DDD-WR", week=4).exists())

    def test_cleared_player_loses_his_status(self):
        summary, _ = self.run_at(et(2025, 9, 28, 11, 0), [("00-AAA-WR", "Doubtful")])
        self.assertEqual(summary["changed"], ["00-AAA-WR", "00-DDD-WR"])
        self.assertFalse(InjuryReport.objects.filter(player_id="00-DDD-WR", week=4).exists())

    def test_model_trained_on_other_features_is_not_used(self):
        from predictor.models import ModelRun

        ModelRun.objects.update(features=["old_feature"])
        summary, _ = self.run_at(et(2025, 9, 28, 11, 0), [("00-DDD-WR", "Out")])
        self.assertEqual(summary["reprojected"], 0)
        self.assertEqual(InjuryReport.objects.get(player_id="00-DDD-WR", week=4).status, "Out")


class InjuryRefreshCommandTests(TestCase):
    def setUp(self):
        populate_db()
        Game.objects.filter(season=2025, week=4).update(kickoff=et(2025, 9, 28, 13, 0))

    def test_skips_quietly_outside_a_game_window(self):
        out = StringIO()
        with mock.patch("predictor.gameday.fetch_statuses") as fetch:
            call_command("injury_refresh", stdout=out)
        fetch.assert_not_called()
        self.assertIn("Skipped", out.getvalue())
        self.assertFalse(RefreshLog.objects.exists())

    def test_forced_run_logs_a_refresh(self):
        out = StringIO()
        with mock.patch("predictor.gameday.fetch_statuses", return_value=statuses([("00-AAA-QB", "Out")])):
            call_command("injury_refresh", "--force", stdout=out)
        log = RefreshLog.objects.get()
        self.assertTrue(log.success)
        self.assertIn("1 newly Out (00-AAA-QB)", log.message)

    def test_missing_kickoffs_load_the_schedule_once(self):
        Game.objects.update(kickoff=None)
        with mock.patch("predictor.gameday.load_schedule", return_value=pd.DataFrame()) as load, \
                mock.patch("predictor.gameday.store_schedule") as store, \
                mock.patch("predictor.gameday.fetch_statuses") as fetch:
            summary = refresh_game_day(now=et(2025, 9, 28, 12, 0))
        load.assert_called_once_with([2025])
        store.assert_called_once()
        fetch.assert_not_called()
        self.assertFalse(summary["ran"])

    def test_window_uses_now(self):
        with mock.patch("predictor.gameday.fetch_statuses", return_value=statuses([])):
            self.assertTrue(refresh_game_day(now=et(2025, 9, 28, 12, 0))["ran"])
            self.assertFalse(refresh_game_day(now=et(2025, 9, 28, 12, 0) + timedelta(days=1))["ran"])
