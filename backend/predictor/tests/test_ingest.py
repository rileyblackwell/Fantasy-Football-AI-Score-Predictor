import pandas as pd
from django.test import TestCase

from predictor.ingest import (
    add_usage,
    clean_ff_opportunity,
    clean_injuries,
    clean_players,
    clean_snap_counts,
    clean_rosters,
    clean_schedule,
    clean_weekly_stats,
    current_season,
    store_injuries,
    store_rosters,
    store_weekly_stats,
)
from predictor.models import InjuryReport, Player, WeeklyStat


def raw_stat(**overrides):
    row = {
        "player_id": "00-1", "player_name": "J.Doe", "player_display_name": "John Doe", "position": "WR",
        "headshot_url": None, "season": 2025, "week": 1, "season_type": "REG", "team": "OAK", "opponent_team": "SD",
        "completions": None, "attempts": 0, "passing_yards": 0, "passing_tds": 0, "passing_interceptions": 0,
        "carries": 1, "rushing_yards": 4.0, "rushing_tds": 0, "targets": 8, "receptions": 6, "receiving_yards": 71.0,
        "receiving_tds": 1, "target_share": 0.25, "fantasy_points": 13.5, "fantasy_points_ppr": 19.5,
    }
    row.update(overrides)
    return row


class CleanWeeklyStatsTests(TestCase):
    def test_keeps_regular_season_skill_players_and_fixes_teams(self):
        raw = pd.DataFrame(
            [
                raw_stat(),
                raw_stat(player_id="00-2", position="LB"),  # defensive player: dropped
                raw_stat(player_id="00-3", season_type="POST"),  # playoffs: dropped
                raw_stat(player_id=None),  # team-level row with no player: dropped
            ]
        )
        df = clean_weekly_stats(raw)
        self.assertEqual(df["player_id"].tolist(), ["00-1"])
        row = df.iloc[0]
        self.assertEqual((row["team"], row["opponent"]), ("LV", "LAC"))
        self.assertEqual(row["name"], "John Doe")
        self.assertEqual(row["completions"], 0)  # nulls become zero
        self.assertAlmostEqual(row["fantasy_points_std"], 13.5)

    def test_duplicate_player_week_keeps_one_row(self):
        raw = pd.DataFrame([raw_stat(fantasy_points_ppr=5.0), raw_stat(fantasy_points_ppr=19.5)])
        df = clean_weekly_stats(raw)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["fantasy_points_ppr"], 19.5)

    def test_store_replaces_season_and_upserts_players(self):
        df = clean_weekly_stats(pd.DataFrame([raw_stat()]))
        store_weekly_stats(df, [2025])
        store_weekly_stats(df.assign(team="KC"), [2025])
        self.assertEqual(WeeklyStat.objects.count(), 1)
        self.assertEqual(Player.objects.get().team, "KC")


class CleanOtherTests(TestCase):
    def test_schedule_regular_season_only_and_team_fix(self):
        raw = pd.DataFrame(
            [
                {"game_id": "a", "game_type": "REG", "season": 2016, "week": 1, "gameday": "2016-09-11",
                 "home_team": "STL", "away_team": "SF", "home_score": 0, "away_score": 28, "spread_line": 2.5,
                 "total_line": 44.0},
                {"game_id": "b", "game_type": "WC", "season": 2016, "week": 19, "gameday": "2017-01-07",
                 "home_team": "SEA", "away_team": "DET", "home_score": 26, "away_score": 6, "spread_line": 8.0,
                 "total_line": 43.0},
            ]
        )
        df = clean_schedule(raw)
        self.assertEqual(df["game_id"].tolist(), ["a"])
        self.assertEqual(df.iloc[0]["home_team"], "LA")

    def test_injuries_keep_most_severe_status(self):
        base = {"season": 2026, "season_type": "REG", "week": 10, "gsis_id": "00-1", "report_primary_injury": "Knee"}
        raw = pd.DataFrame(
            [
                {**base, "report_status": "Questionable"},
                {**base, "report_status": "Out"},
                {**base, "gsis_id": "00-2", "report_status": None},  # practice report only: dropped
            ]
        )
        df = clean_injuries(raw)
        self.assertEqual(df[["player_id", "status"]].values.tolist(), [["00-1", "Out"]])

    def test_injuries_before_2025_use_game_type(self):
        # nflverse leaves season_type empty before 2025; game_type still marks regular-season weeks.
        raw = pd.DataFrame(
            [
                {"season": 2018, "season_type": None, "game_type": "REG", "week": 4, "gsis_id": "00-1",
                 "report_primary_injury": "Ankle", "report_status": "Out"},
                {"season": 2018, "season_type": None, "game_type": "WC", "week": 18, "gsis_id": "00-1",
                 "report_primary_injury": "Ankle", "report_status": "Out"},
            ]
        )
        self.assertEqual(clean_injuries(raw)[["season", "week"]].values.tolist(), [[2018, 4]])

    def test_snap_counts_and_expected_points_attach_to_stat_rows(self):
        players = clean_players(
            pd.DataFrame(
                [{"gsis_id": "00-1", "pfr_id": "DoeJo00", "birth_date": "1998-05-02", "rookie_season": 2020,
                  "draft_pick": None}]
            )
        )
        self.assertTrue(pd.isna(players.iloc[0]["draft_pick"]))
        snaps = clean_snap_counts(
            pd.DataFrame(
                [
                    {"game_type": "REG", "season": 2025, "week": 1, "pfr_player_id": "DoeJo00", "offense_pct": 0.83},
                    {"game_type": "WC", "season": 2025, "week": 19, "pfr_player_id": "DoeJo00", "offense_pct": 0.9},
                    {"game_type": "REG", "season": 2025, "week": 1, "pfr_player_id": "Unknown", "offense_pct": 0.5},
                ]
            ),
            players,
        )
        self.assertEqual(snaps[["player_id", "offense_snap_pct"]].values.tolist(), [["00-1", 0.83]])
        opp = clean_ff_opportunity(
            pd.DataFrame(
                [{"player_id": "00-1", "season": "2025", "week": 1, "total_fantasy_points_exp": 14.2,
                  "rec_air_yards": 55.0}]
            )
        )
        stats = clean_weekly_stats(pd.DataFrame([raw_stat()]))
        merged = add_usage(stats, snaps, opp)
        self.assertAlmostEqual(merged.iloc[0]["offense_snap_pct"], 0.83)
        self.assertAlmostEqual(merged.iloc[0]["expected_ppr"], 14.2)
        store_weekly_stats(merged, [2025])
        self.assertAlmostEqual(WeeklyStat.objects.get().expected_ppr, 14.2)

    def test_rosters_latest_week_wins_and_store_skips_unknown_injuries(self):
        raw = pd.DataFrame(
            [
                {"gsis_id": "00-1", "position": "RB", "team": "NYJ", "week": 3, "full_name": "A B",
                 "status": "ACT", "headshot_url": None},
                {"gsis_id": "00-1", "position": "RB", "team": "OAK", "week": 9, "full_name": "A B",
                 "status": "RES", "headshot_url": "http://x/y.png"},
            ]
        )
        rosters = clean_rosters(raw)
        store_rosters(rosters)
        player = Player.objects.get(pk="00-1")
        self.assertEqual((player.team, player.roster_status), ("LV", "RES"))

        injuries = pd.DataFrame(
            [{"player_id": "00-1", "season": 2026, "week": 9, "status": "Out", "injury": "Knee"},
             {"player_id": "00-404", "season": 2026, "week": 9, "status": "Out", "injury": ""}]
        )
        self.assertEqual(store_injuries(injuries, 2026), 1)
        self.assertEqual(InjuryReport.objects.get().player_id, "00-1")

    def test_current_season_rolls_over_in_september(self):
        from datetime import date

        self.assertEqual(current_season(date(2026, 8, 31)), 2025)
        self.assertEqual(current_season(date(2026, 9, 1)), 2026)
        self.assertEqual(current_season(date(2027, 1, 15)), 2026)


class DefenseTests(TestCase):
    def test_points_allowed_tiers(self):
        from predictor.ingest import points_allowed_score

        self.assertEqual([points_allowed_score(p) for p in (0, 6, 13, 20, 27, 34, 35)], [10, 7, 4, 1, 0, -1, -4])

    def test_clean_dst_stats_scores_team_defense(self):
        from predictor.ingest import clean_dst_stats

        team_stats = pd.DataFrame(
            [
                {"season": 2025, "week": 1, "season_type": "REG", "team": "OAK", "opponent_team": "KC",
                 "def_sacks": 3.0, "def_interceptions": 1, "fumble_recovery_opp": 1, "def_tds": 1,
                 "special_teams_tds": 0, "def_safeties": 0, "def_punt_blocks": 0, "def_fg_blocks": 1},
                {"season": 2025, "week": 1, "season_type": "POST", "team": "KC", "opponent_team": "LV",
                 "def_sacks": 9.0},
            ]
        )
        schedule = pd.DataFrame(
            [{"season": 2025, "week": 1, "home_team": "LV", "away_team": "KC", "home_score": 24, "away_score": 10}]
        )
        teams = pd.DataFrame([{"abbr": "LV", "name": "Las Vegas Raiders", "logo_url": "http://logo"}])
        df = clean_dst_stats(team_stats, schedule, teams)
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual((row["player_id"], row["name"], row["position"]), ("DST-LV", "Las Vegas Raiders D/ST", "DST"))
        self.assertEqual(row["points_allowed"], 10)
        # 3 sacks + 2 INT + 2 FR + 6 TD + 2 block + 4 (10 points allowed) = 19
        self.assertEqual(row["fantasy_points_ppr"], 19.0)
        self.assertEqual(row["fantasy_points_std"], 19.0)


class TeamTests(TestCase):
    def test_relocated_franchise_keeps_current_name(self):
        from predictor.ingest import clean_teams

        raw = pd.DataFrame(
            [
                {"team_abbr": "LA", "team_name": "Los Angeles Rams", "team_nick": "Rams", "team_color": "#003594",
                 "team_color2": "#FFD100", "team_logo_espn": "http://la"},
                {"team_abbr": "STL", "team_name": "St. Louis Rams", "team_nick": "Rams", "team_color": "#000",
                 "team_color2": "#fff", "team_logo_espn": "http://stl"},
            ]
        )
        df = clean_teams(raw)
        self.assertEqual(df[["abbr", "name"]].values.tolist(), [["LA", "Los Angeles Rams"]])
