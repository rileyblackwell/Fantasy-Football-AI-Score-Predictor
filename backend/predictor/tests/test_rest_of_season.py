from django.db.models import F
from django.test import TestCase

from predictor.models import Game, InjuryReport, Player, Prediction, WeeklyStat
from predictor.pipeline import run_pipeline
from predictor.rest_of_season import MAX_SWING, matchup_factors
from predictor.tests.factories import populate_db

# populate_db plays 2025 through week 3 of 6, so weeks 4-6 are left. Pairings by week:
# 4: AAA-BBB, CCC-DDD   5: AAA-CCC, BBB-DDD   6: AAA-DDD, BBB-CCC


def get(client, **params):
    return client.get("/api/rest-of-season", params).json()


def player(client, player_id, **params):
    return get(client, ids=player_id, **params)["players"][0]


class EmptyRestOfSeasonTests(TestCase):
    def test_no_data_yet(self):
        data = get(self.client)
        self.assertIsNone(data["season"])
        self.assertEqual(data["players"], [])


class RestOfSeasonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        populate_db()
        InjuryReport.objects.create(player_id="00-AAA-WR", season=2025, week=4, status="Out", injury="Ankle")
        run_pipeline(num_rounds=10)

    def test_pool_lists_every_player_with_totals_only(self):
        data = get(self.client)
        self.assertEqual((data["season"], data["from_week"], data["through_week"], data["last_week"]), (2025, 4, 6, 6))
        self.assertEqual(len(data["players"]), 4 * 5)  # four teams, one player per position
        totals = [p["total"] for p in data["players"]]
        self.assertEqual(totals, sorted(totals, reverse=True))
        self.assertNotIn("games", data["players"][0])
        self.assertTrue(all(p["games_left"] == 3 for p in data["players"]))

    def test_upcoming_week_uses_the_model_projection_unchanged(self):
        qb = player(self.client, "00-AAA-QB")
        projection = Prediction.objects.get(player_id="00-AAA-QB", season=2025, week=4, is_backtest=False)
        self.assertEqual(qb["basis"], "projection")
        self.assertEqual([(g["week"], g["opponent"], g["is_home"]) for g in qb["games"]], [(4, "BBB", True), (5, "CCC", True), (6, "DDD", True)])
        self.assertEqual(qb["games"][0]["points"], round(projection.points_ppr, 1))
        self.assertAlmostEqual(qb["total"], sum(g["points"] for g in qb["games"]), delta=0.2)

    def test_bye_week_adds_no_game(self):
        before = player(self.client, "00-AAA-QB")
        Game.objects.filter(season=2025, week=5, home_team="AAA").delete()
        after = player(self.client, "00-AAA-QB")
        self.assertEqual([g["week"] for g in after["games"]], [4, 6])
        self.assertEqual(after["bye_week"], 5)
        self.assertIsNone(before["bye_week"])
        self.assertLess(after["total"], before["total"])

    def test_through_week_limits_and_clamps(self):
        self.assertEqual([g["week"] for g in player(self.client, "00-AAA-QB", through=5)["games"]], [4, 5])
        self.assertEqual(get(self.client, through=99)["through_week"], 6)
        self.assertEqual(get(self.client, through=1)["through_week"], 4)
        self.assertEqual(self.client.get("/api/rest-of-season", {"through": "x"}).status_code, 400)

    def test_player_ruled_out_scores_zero_this_week_then_returns(self):
        wr = player(self.client, "00-AAA-WR")
        self.assertEqual(wr["injury_status"], "Out")
        # Only backtest projections exist before week 4 here, so the rate falls back to the season average.
        self.assertEqual(wr["basis"], "season_avg")
        self.assertEqual(wr["games"][0]["points"], 0)
        self.assertTrue(all(g["points"] > 0 for g in wr["games"][1:]))

    def test_earlier_projection_is_used_when_there_is_no_game_this_week(self):
        # A live projection published before week 3 (the factory's week-3 row is a backtest).
        Prediction.objects.filter(player_id="00-AAA-WR", season=2025, week=3).update(
            is_backtest=False, opponent="DDD", points_ppr=14.0, points_half=12.0, points_std=10.0
        )
        wr = player(self.client, "00-AAA-WR")
        self.assertEqual(wr["basis"], "recent_projection")
        factors = matchup_factors(2025)
        rate = 14.0 / factors[("DDD", "WR")]
        self.assertEqual(wr["per_game"], round(rate, 1))
        self.assertEqual(wr["games"][1]["points"], round(rate * factors[("CCC", "WR")], 1))

    def test_inactive_player_gets_zero(self):
        Player.objects.filter(player_id="00-BBB-RB").update(roster_status="RES")
        rb = player(self.client, "00-BBB-RB")
        self.assertEqual((rb["basis"], rb["total"]), ("inactive", 0))

    def test_pool_drops_last_seasons_players_who_left(self):
        WeeklyStat.objects.filter(player_id="00-DDD-TE", season=2025).delete()
        self.assertIn("00-DDD-TE", {p["player_id"] for p in get(self.client)["players"]})
        Player.objects.filter(player_id="00-DDD-TE").update(roster_status="CUT")
        self.assertNotIn("00-DDD-TE", {p["player_id"] for p in get(self.client)["players"]})

    def test_scoring_format(self):
        ppr = player(self.client, "00-CCC-WR")["total"]
        std = player(self.client, "00-CCC-WR", scoring="std")["total"]
        self.assertLess(std, ppr)

    def test_ids_filter_ignores_unknown(self):
        data = get(self.client, ids="00-AAA-QB,nope,DST-BBB")
        self.assertEqual({p["player_id"] for p in data["players"]}, {"00-AAA-QB", "DST-BBB"})


class MatchupFactorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        populate_db()

    def test_soft_defense_raises_points_within_the_cap(self):
        WeeklyStat.objects.filter(season=2025, opponent="DDD", position="QB").update(
            fantasy_points_ppr=F("fantasy_points_ppr") + 15
        )
        factors = matchup_factors(2025)
        self.assertGreater(factors[("DDD", "QB")], 1)
        self.assertLess(factors[("CCC", "QB")], 1)
        self.assertTrue(all(1 - MAX_SWING <= f <= 1 + MAX_SWING for f in factors.values()))
