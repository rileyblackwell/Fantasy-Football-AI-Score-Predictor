from django.test import TestCase, override_settings

from predictor.models import Game, InjuryReport
from predictor.pipeline import run_pipeline
from predictor.views import bye_weeks
from predictor.tests.factories import populate_db


class EmptyApiTests(TestCase):
    def test_endpoints_work_before_any_data(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        summary = self.client.get("/api/summary").json()
        self.assertIsNone(summary["week"])
        self.assertIsNone(summary["model"])
        self.assertEqual(self.client.get("/api/predictions").json()["results"], [])


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        populate_db()
        InjuryReport.objects.create(player_id="00-AAA-WR", season=2025, week=4, status="Out", injury="Ankle")
        run_pipeline(num_rounds=10)

    def test_summary(self):
        data = self.client.get("/api/summary").json()
        self.assertEqual((data["season"], data["week"]), (2025, 4))
        self.assertEqual(data["positions"], ["QB", "RB", "WR", "TE", "DST"])
        self.assertIn("model_mae", data["model"]["metrics"])
        self.assertTrue(data["model"]["feature_importance"])
        self.assertIn({"season": 2025, "week": 4, "is_backtest": False}, data["weeks"])

    def test_predictions_default_to_upcoming_week_sorted(self):
        data = self.client.get("/api/predictions").json()
        self.assertEqual(data["week"], 4)
        projected = [r["projected"] for r in data["results"]]
        self.assertEqual(projected, sorted(projected, reverse=True))
        wr = next(r for r in data["results"] if r["player_id"] == "00-AAA-WR")
        self.assertEqual(wr["injury_status"], "Out")
        self.assertIsNone(wr["actual"])

    def test_predictions_include_bye_week(self):
        self.assertIsNone(self.client.get("/api/predictions").json()["results"][0]["bye_week"])
        # Week 5 of 2025 pairs AAA with CCC; drop that game so both teams are off that week.
        Game.objects.filter(season=2025, week=5, home_team="AAA").delete()
        rows = self.client.get("/api/predictions").json()["results"]
        self.assertEqual({r["team"] for r in rows if r["bye_week"] == 5}, {"AAA", "CCC"})
        self.assertTrue(all(r["bye_week"] is None for r in rows if r["team"] in ("BBB", "DDD")))

    def test_predictions_filters_and_scoring(self):
        rbs = self.client.get("/api/predictions", {"position": "rb"}).json()["results"]
        self.assertEqual({r["position"] for r in rbs}, {"RB"})
        team = self.client.get("/api/predictions", {"search": "bbb"}).json()["results"]
        self.assertEqual({r["team"] for r in team}, {"BBB"})
        ppr = {r["player_id"]: r["projected"] for r in self.client.get("/api/predictions").json()["results"]}
        std = {r["player_id"]: r["projected"] for r in self.client.get("/api/predictions", {"scoring": "std"}).json()["results"]}
        self.assertNotEqual(ppr, std)

    def test_past_week_includes_actual_scores(self):
        data = self.client.get("/api/predictions", {"season": 2025, "week": 2}).json()
        self.assertTrue(all(r["actual"] is not None and r["is_backtest"] for r in data["results"]))

    def test_bad_week_parameter(self):
        self.assertEqual(self.client.get("/api/predictions", {"week": "abc"}).status_code, 400)

    def test_player_detail(self):
        data = self.client.get("/api/players/00-AAA-QB").json()
        self.assertEqual(data["name"], "AAA QB")
        self.assertEqual(data["games_played"], 3)
        self.assertEqual([w["week"] for w in data["weeks"]], [1, 2, 3, 4])
        self.assertIsNone(data["weeks"][-1]["actual"])
        self.assertIsNotNone(data["weeks"][-1]["projected"])
        self.assertIn("pass", data["weeks"][0]["line"])

    def test_unknown_player_404(self):
        self.assertEqual(self.client.get("/api/players/nope").status_code, 404)


class SpaTests(TestCase):
    def test_client_routes_serve_index_or_explain_missing_build(self):
        res = self.client.get("/players/00-1")
        self.assertIn(res.status_code, (200, 404))
        if res.status_code == 200:
            self.assertIn(b'<div id="app">', b"".join(res.streaming_content))

    def test_missing_build_message(self):
        from pathlib import Path

        with override_settings(FRONTEND_DIST=Path("/nonexistent")):
            res = self.client.get("/about")
        self.assertEqual(res.status_code, 404)
        self.assertIn("Frontend not built", res.json()["detail"])


class AccuracyApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        populate_db()
        run_pipeline(num_rounds=10)

    def test_accuracy_compares_past_predictions_with_actuals(self):
        data = self.client.get("/api/accuracy").json()
        self.assertEqual(data["season"], 2025)
        self.assertEqual([w["week"] for w in data["weeks"]], [1, 2, 3])
        self.assertEqual(data["overall"]["games"], 60)
        self.assertGreaterEqual(data["overall"]["mae"], 0)
        self.assertIn("DST", data["by_position"])
        self.assertLessEqual(len(data["biggest_misses"]), 5)

    def test_dst_player_detail_has_defense_line(self):
        data = self.client.get("/api/players/DST-AAA").json()
        self.assertEqual(data["position"], "DST")
        self.assertIn("pts allowed", data["weeks"][0]["line"]["dst"])


class ByeWeekTests(TestCase):
    def game(self, week, home, away):
        Game.objects.create(game_id=f"2026_{week:02d}_{away}_{home}", season=2026, week=week, home_team=home, away_team=away)

    def test_bye_is_the_first_week_without_a_game(self):
        self.game(1, "AAA", "BBB")
        self.game(1, "CCC", "DDD")
        self.game(2, "AAA", "CCC")
        self.game(3, "BBB", "DDD")
        self.game(3, "AAA", "CCC")
        self.assertEqual(bye_weeks(2026), {"BBB": 2, "DDD": 2})

    def test_no_schedule_means_no_byes(self):
        self.assertEqual(bye_weeks(2030), {})
