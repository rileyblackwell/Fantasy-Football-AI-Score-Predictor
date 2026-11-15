from django.test import SimpleTestCase, TestCase

from predictor.models import InjuryReport, Player, Prediction, WeeklyStat
from predictor.tests.factories import populate_db
from predictor.waivers import usage_trend


def games(snaps, targets, start_week=1):
    return [
        {"week": start_week + i, "offense_snap_pct": s, "target_share": t}
        for i, (s, t) in enumerate(zip(snaps, targets))
    ]


class UsageTrendTests(SimpleTestCase):
    def test_flags_rising_snaps_and_targets(self):
        trend = usage_trend(games([0.4, 0.4, 0.8, 0.8, 0.8], [0.08, 0.08, 0.2, 0.2, 0.2]), "WR", 5)
        self.assertTrue(trend["rising_snaps"])
        self.assertTrue(trend["rising_targets"])
        self.assertEqual(trend["snap_share"], {"recent": 0.8, "prior": 0.4, "change": 0.4})
        self.assertEqual(trend["target_share"]["change"], 0.12)
        self.assertAlmostEqual(trend["trend_score"], 0.4 + 2 * 0.12)
        self.assertEqual((trend["games_recent"], trend["games_prior"]), (3, 2))

    def test_flat_or_falling_usage_is_not_flagged(self):
        self.assertIsNone(usage_trend(games([0.7] * 5, [0.2] * 5), "WR", 5))
        self.assertIsNone(usage_trend(games([0.9, 0.9, 0.5, 0.5, 0.5], [0.2] * 5), "RB", 5))

    def test_small_rises_and_tiny_roles_are_ignored(self):
        # +5 points of snaps is under the threshold.
        self.assertIsNone(usage_trend(games([0.6, 0.6, 0.65, 0.65, 0.65], [0.1] * 5), "WR", 5))
        # 5% to 20% of snaps is a big jump, but 20% is still no role.
        self.assertIsNone(usage_trend(games([0.05, 0.05, 0.2, 0.2, 0.2], [0.01] * 5), "WR", 5))

    def test_needs_enough_games_and_a_recent_game(self):
        self.assertIsNone(usage_trend(games([0.4, 0.8, 0.8, 0.8], [0.1] * 4), "WR", 4))
        # Last game was week 5 but week 8 is complete: hurt or benched since.
        self.assertIsNone(usage_trend(games([0.4, 0.4, 0.8, 0.8, 0.8], [0.1] * 5), "WR", 8))
        self.assertIsNotNone(usage_trend(games([0.4, 0.4, 0.8, 0.8, 0.8], [0.1] * 5), "WR", 6))

    def test_quarterbacks_are_judged_on_snaps_only(self):
        trend = usage_trend(games([0.2, 0.2, 1.0, 1.0, 1.0], [None] * 5), "QB", 5)
        self.assertTrue(trend["rising_snaps"])
        self.assertIsNone(trend["target_share"]["change"])
        # Even with a target spike, a QB is only flagged for snaps.
        self.assertIsNone(usage_trend(games([1.0] * 5, [0.0, 0.0, 0.3, 0.3, 0.3]), "QB", 5))

    def test_missing_snap_data_falls_back_to_targets(self):
        trend = usage_trend(games([None] * 5, [0.1, 0.1, 0.2, 0.2, 0.2]), "TE", 5)
        self.assertFalse(trend["rising_snaps"])
        self.assertTrue(trend["rising_targets"])
        self.assertIsNone(trend["snap_share"]["change"])


class WaiversApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 2025 is played through week 7; projections are for week 8.
        populate_db(weeks=8, played_through=(2025, 7))
        stats = WeeklyStat.objects.filter(season=2025).exclude(position="DST")
        stats.update(offense_snap_pct=0.6, target_share=0.15)

        def set_usage(player_id, weeks, snaps, targets):
            WeeklyStat.objects.filter(player_id=player_id, season=2025, week__in=weeks).update(
                offense_snap_pct=snaps, target_share=targets
            )

        # AAA WR: a part-timer who became a starter. Both snaps and targets climb.
        set_usage("00-AAA-WR", [1, 2, 3, 4], 0.4, 0.08)
        set_usage("00-AAA-WR", [5, 6, 7], 0.85, 0.24)
        # BBB RB: more snaps, same targets.
        set_usage("00-BBB-RB", [1, 2, 3, 4], 0.35, 0.15)
        set_usage("00-BBB-RB", [5, 6, 7], 0.65, 0.15)
        # CCC QB: backup who took over.
        set_usage("00-CCC-QB", [1, 2, 3, 4], 0.1, None)
        set_usage("00-CCC-QB", [5, 6, 7], 1.0, None)
        # DDD WR: was rising, then stopped playing after week 5.
        set_usage("00-DDD-WR", [1, 2], 0.3, 0.05)
        set_usage("00-DDD-WR", [3, 4, 5], 0.9, 0.3)
        WeeklyStat.objects.filter(player_id="00-DDD-WR", season=2025, week__in=[6, 7]).delete()

        for rank, player in enumerate(Player.objects.exclude(position="DST").order_by("player_id")):
            Prediction.objects.create(
                player=player, season=2025, week=8, team=player.team, opponent="ZZZ", is_home=True,
                points_ppr=20 - rank * 0.5, points_half=18 - rank * 0.5, points_std=16 - rank * 0.5,
            )
        InjuryReport.objects.create(player_id="00-BBB-RB", season=2025, week=8, status="Questionable", injury="Knee")

    def test_lists_rising_players_strongest_first(self):
        data = self.client.get("/api/waivers").json()
        self.assertEqual((data["season"], data["week"], data["through_week"]), (2025, 8, 7))
        ids = [r["player_id"] for r in data["results"]]
        self.assertEqual(ids, ["00-CCC-QB", "00-AAA-WR", "00-BBB-RB"])
        wr = data["results"][1]
        self.assertTrue(wr["rising_snaps"] and wr["rising_targets"])
        self.assertEqual(wr["snap_share"]["recent"], 0.85)
        self.assertEqual(wr["opponent"], "ZZZ")
        self.assertIsNotNone(wr["projected"])
        self.assertEqual(wr["position_rank"], 1)
        self.assertEqual([h["week"] for h in wr["history"]], list(range(1, 8)))

    def test_player_without_a_projection_is_ranked_from_their_latest_one(self):
        # AAA WR is on bye in week 8, but was projected well above every other WR in week 7.
        Prediction.objects.filter(player_id="00-AAA-WR", week=8).delete()
        Prediction.objects.create(
            player_id="00-AAA-WR", season=2025, week=6, team="AAA", opponent="BBB", is_home=True,
            points_ppr=1.0, points_half=1.0, points_std=1.0,
        )
        Prediction.objects.create(
            player_id="00-AAA-WR", season=2025, week=7, team="AAA", opponent="BBB", is_home=True,
            points_ppr=99.0, points_half=99.0, points_std=99.0,
        )
        wr = next(r for r in self.client.get("/api/waivers").json()["results"] if r["player_id"] == "00-AAA-WR")
        self.assertIsNone(wr["projected"])
        self.assertEqual((wr["position_rank"], wr["rank_from_week"]), (1, 7))
        # A player with this week's projection keeps this week's rank.
        rb = next(r for r in self.client.get("/api/waivers").json()["results"] if r["player_id"] == "00-BBB-RB")
        self.assertIsNone(rb["rank_from_week"])
        self.assertIsNotNone(rb["position_rank"])

    def test_player_with_no_projection_at_all_has_no_rank(self):
        Prediction.objects.filter(player_id="00-AAA-WR").delete()
        wr = next(r for r in self.client.get("/api/waivers").json()["results"] if r["player_id"] == "00-AAA-WR")
        self.assertIsNone(wr["position_rank"])
        self.assertIsNone(wr["rank_from_week"])

    def test_includes_injury_status(self):
        rb = next(r for r in self.client.get("/api/waivers").json()["results"] if r["player_id"] == "00-BBB-RB")
        self.assertEqual((rb["injury_status"], rb["injury"]), ("Questionable", "Knee"))
        self.assertFalse(rb["rising_targets"])

    def test_position_filter_and_scoring(self):
        wrs = self.client.get("/api/waivers", {"position": "wr"}).json()["results"]
        self.assertEqual([r["player_id"] for r in wrs], ["00-AAA-WR"])
        # Use the receiver: a quarterback with no catches scores the same in every format.
        ppr = self.client.get("/api/waivers", {"position": "WR"}).json()["results"][0]
        std = self.client.get("/api/waivers", {"position": "WR", "scoring": "std"}).json()["results"][0]
        self.assertNotEqual(ppr["projected"], std["projected"])
        self.assertNotEqual(ppr["points_recent"], std["points_recent"])

    def test_only_uses_games_before_the_projected_week(self):
        # Looking at week 6 means only weeks 1-5 have been played, so AAA WR has 2 risen games in the window.
        data = self.client.get("/api/waivers", {"week": 6}).json()
        self.assertEqual(data["through_week"], 5)
        self.assertIn("00-DDD-WR", [r["player_id"] for r in data["results"]])

    def test_bad_parameters(self):
        self.assertEqual(self.client.get("/api/waivers", {"week": "x"}).status_code, 400)


class EmptyWaiversTests(TestCase):
    def test_no_data_yet(self):
        data = self.client.get("/api/waivers").json()
        self.assertEqual(data["results"], [])
        self.assertIsNone(data["week"])
