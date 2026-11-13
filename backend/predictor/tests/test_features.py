import math

import pandas as pd
from django.test import SimpleTestCase

from predictor.features import FEATURES, build_features, team_games
from predictor.tests.factories import schedule, weekly_stats


class FeatureTests(SimpleTestCase):
    def setUp(self):
        self.games = schedule([2024, 2025], weeks=6, played_through=(2025, 3))
        self.stats = weekly_stats(self.games)

    def row(self, frame, player, season, week):
        sel = frame[(frame.player_id == player) & (frame.season == season) & (frame.week == week)]
        self.assertEqual(len(sel), 1)
        return sel.iloc[0]

    def test_features_only_use_earlier_games(self):
        frame = build_features(self.stats, self.games)
        pts = self.stats.set_index(["player_id", "season", "week"])["fantasy_points_ppr"]
        r = self.row(frame, "00-AAA-WR", 2025, 3)
        self.assertAlmostEqual(r.ppr_last1, pts[("00-AAA-WR", 2025, 2)])
        expected_last3 = (pts[("00-AAA-WR", 2025, 2)] + pts[("00-AAA-WR", 2025, 1)] + pts[("00-AAA-WR", 2024, 6)]) / 3
        self.assertAlmostEqual(r.ppr_last3, expected_last3)
        self.assertAlmostEqual(r.ppr_season_avg, (pts[("00-AAA-WR", 2025, 2)] + pts[("00-AAA-WR", 2025, 1)]) / 2)
        self.assertAlmostEqual(r.ppr_prev_season_avg, pts.loc["00-AAA-WR", 2024].mean())
        self.assertEqual(r.games_this_season, 2)

    def test_first_career_game_has_no_history(self):
        frame = build_features(self.stats, self.games)
        r = self.row(frame, "00-AAA-WR", 2024, 1)
        self.assertTrue(math.isnan(r.ppr_last1))
        self.assertEqual(r.career_games, 0)

    def test_upcoming_rows_get_features_and_no_target(self):
        upcoming = pd.DataFrame(
            [{"player_id": "00-AAA-QB", "season": 2025, "week": 4, "team": "AAA", "opponent": "BBB", "position": "QB"}]
        )
        frame = build_features(self.stats, self.games, upcoming)
        r = self.row(frame, "00-AAA-QB", 2025, 4)
        self.assertFalse(r.is_played)
        self.assertTrue(math.isnan(r.fantasy_points_ppr))
        last = self.stats[(self.stats.player_id == "00-AAA-QB") & (self.stats.season == 2025) & (self.stats.week == 3)]
        self.assertAlmostEqual(r.ppr_last1, last.fantasy_points_ppr.iloc[0])
        self.assertEqual(r.is_home, 1)
        self.assertAlmostEqual(r.implied_team_total, 24.0)  # (45 + 3) / 2
        for col in FEATURES:
            self.assertIn(col, frame.columns)

    def test_opponent_allowed_uses_only_earlier_weeks(self):
        frame = build_features(self.stats, self.games)
        # Week 1 of the first season: nothing is known about any defense yet.
        self.assertTrue(frame[(frame.season == 2024) & (frame.week == 1)]["opp_allowed_ppr_last8"].isna().all())
        # BBB's defense in 2024 week 2 has allowed exactly one week of WR points (to AAA in week 1).
        r = self.row(frame, "00-DDD-WR", 2024, 2)
        self.assertEqual(r.opponent, "BBB")
        allowed = self.stats[(self.stats.opponent == "BBB") & (self.stats.position == "WR") & (self.stats.season == 2024) & (self.stats.week == 1)]
        self.assertAlmostEqual(r.opp_allowed_ppr_last8, allowed.fantasy_points_ppr.sum())

    def test_team_games_implied_totals_sum_to_game_total(self):
        tg = team_games(self.games.head(1))
        self.assertAlmostEqual(tg.implied_team_total.sum(), 45.0)
        self.assertEqual(sorted(tg.team_spread.tolist()), [-3.0, 3.0])
