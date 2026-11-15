import io
import json
from datetime import datetime, timedelta
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

import pandas as pd
from django.core.management import call_command
from django.test import TestCase

from predictor.gameday import (
    espn_athlete_id,
    fetch_statuses,
    game_windows,
    in_game_window,
    parse_espn_injuries,
    refresh_game_day,
)
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


def statuses(rows, source="espn"):
    frame = pd.DataFrame(
        [{"player_id": p, "season": 2025, "week": 4, "status": s, "injury": "Knee"} for p, s in rows],
        columns=["player_id", "season", "week", "status", "injury"],
    )
    return frame, source


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
        # Re-projected rows keep their score ranges.
        self.assertIsNotNone(Prediction.objects.get(player_id="00-DDD-WR", season=2025, week=4).floor_ppr)

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
        self.assertIn("(espn)", log.message)

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


def espn_item(espn_id, status, injury="Knee", with_id=False):
    """One injury item shaped like ESPN's feed (Nov 15, 2026): the athlete has no id field, so the id
    is only in the note's reference, the page links and the headshot."""
    athlete = {
        "displayName": f"Player {espn_id}",
        "links": [{"href": f"https://www.espn.com/nfl/player/_/id/{espn_id}/player"}],
        "headshot": {"href": f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"},
        "notes": {"items": [{"injury": {"$ref": f"http://sports.core.api.espn.pvt/v2/sports/football/leagues/nfl/seasons/2026/athletes/{espn_id}/injuries/647675?lang=en"}}]},
        "status": {"id": "1", "name": "Active"},
    }
    if with_id:
        athlete["id"] = espn_id
    return {
        "id": "647675",
        "status": status,
        "date": "2026-11-14T02:25Z",
        "athlete": athlete,
        "type": {"name": "INJURY_STATUS_" + status.upper()},
        "details": {"fantasyStatus": {"description": status.upper()}, "type": injury},
    }


def espn_feed(items, teams=32):
    entries = [{"id": str(i), "displayName": f"Team {i}", "injuries": []} for i in range(teams)]
    entries[0]["injuries"] = items
    return {"timestamp": "2026-11-15T12:00:00Z", "status": "success", "injuries": entries}


class EspnFeedTests(TestCase):
    MAP = {"4709718": "00-0041113", "4240619": "00-0037804", "4367199": "00-0038571", "3886633": "00-0035258"}

    def test_athlete_id_comes_from_the_note_links_or_headshot(self):
        item = espn_item("4709718", "Out")
        self.assertEqual(espn_athlete_id(item["athlete"]), "4709718")
        self.assertEqual(espn_athlete_id({"headshot": {"href": "https://x/full/3886633.png"}}), "3886633")
        self.assertEqual(espn_athlete_id(espn_item("1", "Out", with_id=True)["athlete"]), "1")
        self.assertIsNone(espn_athlete_id({}))

    def test_statuses_map_to_game_designations(self):
        feed = espn_feed([
            espn_item("4709718", "Questionable"),
            espn_item("4240619", "Injured Reserve"),
            espn_item("4367199", "Out", "Ankle"),
            espn_item("3886633", "Day-To-Day"),  # not a game designation
            espn_item("999", "Out"),  # not one of our players
        ])
        df = parse_espn_injuries(feed, self.MAP, 2026, 11)
        got = dict(zip(df["player_id"], df["status"]))
        self.assertEqual(got, {"00-0041113": "Questionable", "00-0037804": "Out", "00-0038571": "Out"})
        self.assertEqual(df.set_index("player_id").loc["00-0038571", "injury"], "Ankle")
        self.assertTrue((df["week"] == 11).all())

    def test_most_severe_listing_wins(self):
        feed = espn_feed([espn_item("4709718", "Questionable"), espn_item("4709718", "Out")])
        self.assertEqual(parse_espn_injuries(feed, self.MAP, 2026, 11)["status"].tolist(), ["Out"])

    def test_a_broken_response_is_not_used(self):
        self.assertIsNone(parse_espn_injuries({}, self.MAP, 2026, 11))
        self.assertIsNone(parse_espn_injuries({"injuries": "x"}, self.MAP, 2026, 11))
        self.assertIsNone(parse_espn_injuries(espn_feed([espn_item("4709718", "Out")], teams=3), self.MAP, 2026, 11))


class StatusSourceTests(TestCase):
    def setUp(self):
        populate_db()
        from predictor.models import Player

        Player.objects.filter(pk="00-AAA-RB").update(espn_id="4709718")

    def nflverse(self):
        return pd.DataFrame(
            [{"player_id": "00-AAA-WR", "season": 2025, "week": 4, "status": "Questionable", "injury": "Hip"},
             {"player_id": "00-AAA-TE", "season": 2025, "week": 3, "status": "Out", "injury": "Hip"}]
        )

    def test_espn_is_used_when_it_answers(self):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(espn_feed([espn_item("4709718", "Out")])).encode())
        with mock.patch("predictor.gameday.urllib.request.urlopen", return_value=response), \
                mock.patch("predictor.gameday.load_injuries") as nflverse:
            df, source = fetch_statuses(2025, 4)
        self.assertEqual(source, "espn")
        self.assertEqual(df.to_dict("records"),
                         [{"player_id": "00-AAA-RB", "season": 2025, "week": 4, "status": "Out", "injury": "Knee"}])
        nflverse.assert_not_called()

    def test_nflverse_is_the_fallback_when_espn_fails(self):
        with mock.patch("predictor.gameday.urllib.request.urlopen", side_effect=OSError("timed out")), \
                mock.patch("predictor.gameday.load_injuries", return_value=self.nflverse()):
            df, source = fetch_statuses(2025, 4)
        self.assertEqual(source, "nflverse")
        self.assertEqual(df["player_id"].tolist(), ["00-AAA-WR"])  # this week's rows only

    def espn_answers(self, *items):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(espn_feed(list(items))).encode())
        return response

    def test_missing_espn_ids_are_loaded_once_so_espn_works_on_the_first_game_day(self):
        from predictor.models import Player

        Player.objects.update(espn_id="")
        table = pd.DataFrame(
            [{"player_id": "00-AAA-RB", "pfr_player_id": "X", "birth_date": None, "rookie_season": 2020,
              "draft_pick": 12, "espn_id": "4709718"}]
        )
        with mock.patch("predictor.gameday.load_players", return_value=table) as players, \
                mock.patch("predictor.gameday.urllib.request.urlopen",
                           side_effect=lambda *a, **k: self.espn_answers(espn_item("4709718", "Out"))), \
                mock.patch("predictor.gameday.load_injuries") as nflverse:
            df, source = fetch_statuses(2025, 4)
            fetch_statuses(2025, 4)
        self.assertEqual(source, "espn")
        self.assertEqual(df["player_id"].tolist(), ["00-AAA-RB"])
        self.assertEqual(Player.objects.get(pk="00-AAA-RB").espn_id, "4709718")
        players.assert_called_once()  # stored now, so the next hour doesn't download it again
        nflverse.assert_not_called()

    def test_nflverse_is_used_when_espn_ids_cant_be_loaded(self):
        from predictor.models import Player

        Player.objects.update(espn_id="")
        with mock.patch("predictor.gameday.load_players", side_effect=OSError("down")), \
                mock.patch("predictor.gameday.urllib.request.urlopen") as urlopen, \
                mock.patch("predictor.gameday.load_injuries", return_value=self.nflverse()):
            _, source = fetch_statuses(2025, 4)
        urlopen.assert_not_called()
        self.assertEqual(source, "nflverse")


class EspnIdIngestTests(TestCase):
    def test_espn_id_is_kept_from_the_nflverse_players_table(self):
        from predictor.ingest import clean_players, store_player_bios
        from predictor.models import Player

        populate_db()
        players = clean_players(
            pd.DataFrame(
                [{"gsis_id": "00-AAA-RB", "pfr_id": "X", "birth_date": "1998-05-02", "rookie_season": 2020,
                  "draft_pick": 12, "espn_id": "4709718"},
                 {"gsis_id": "00-AAA-WR", "pfr_id": "Y", "birth_date": None, "rookie_season": None,
                  "draft_pick": None, "espn_id": None}]
            )
        )
        self.assertEqual(players["espn_id"].tolist(), ["4709718", ""])
        store_player_bios(players)
        self.assertEqual(Player.objects.get(pk="00-AAA-RB").espn_id, "4709718")
        self.assertEqual(Player.objects.get(pk="00-AAA-WR").espn_id, "")
