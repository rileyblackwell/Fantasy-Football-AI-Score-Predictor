from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from predictor.modeling import STEADY_MAX_SWING, SWINGY_MAX_SWING, consistency
from predictor.models import ModelRun, Prediction
from predictor.pipeline import load_latest_models, run_pipeline
from predictor.tests.factories import populate_db


class ConsistencyLabelTests(SimpleTestCase):
    def test_label_follows_range_width_relative_to_projection(self):
        # 20-point projection: a 10-30 range is a swing of 1.0, steady.
        self.assertEqual(consistency(20, 10, 30), "steady")
        # 12-point projection: 3-22 is a swing of ~1.58, swingy.
        self.assertEqual(consistency(12, 3, 22), "swingy")
        # 6-point projection: 0-14 is a swing of ~2.3, boom or bust.
        self.assertEqual(consistency(6, 0, 14), "boom_bust")

    def test_thresholds_are_exclusive_upper_bounds(self):
        self.assertEqual(consistency(10, 0, 10 * STEADY_MAX_SWING - 0.01), "steady")
        self.assertEqual(consistency(10, 0, 10 * STEADY_MAX_SWING), "swingy")
        self.assertEqual(consistency(10, 0, 10 * SWINGY_MAX_SWING), "boom_bust")

    def test_tiny_projections_do_not_blow_up(self):
        self.assertEqual(consistency(0, 0, 1), "steady")
        self.assertEqual(consistency(0.2, 0, 6), "boom_bust")

    def test_missing_range_has_no_label(self):
        self.assertIsNone(consistency(12, None, None))
        self.assertIsNone(consistency(None, 2, 20))


class RangePipelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        populate_db()
        run_pipeline(num_rounds=20)

    def test_upcoming_projections_carry_a_range_around_them(self):
        upcoming = Prediction.objects.filter(season=2025, week=4, is_backtest=False)
        self.assertTrue(upcoming.exists())
        for p in upcoming:
            for fmt in ("ppr", "half", "std"):
                floor, points, ceiling = getattr(p, f"floor_{fmt}"), getattr(p, f"points_{fmt}"), getattr(p, f"ceiling_{fmt}")
                self.assertIsNotNone(floor)
                self.assertGreaterEqual(floor, 0)
                self.assertLessEqual(floor, points + 0.01)
                self.assertGreaterEqual(ceiling, points - 0.01)

    def test_backtest_rows_have_no_range(self):
        backtest = Prediction.objects.filter(season=2025, is_backtest=True)
        self.assertTrue(backtest.exists())
        self.assertFalse(backtest.exclude(floor_ppr=None).exists())

    def test_range_boosters_round_trip_through_database(self):
        models = load_latest_models()
        self.assertTrue(models.has_ranges)
        self.assertEqual(set(models.boosters), {"ppr", "std"})
        self.assertEqual(set(models.range_boosters), {"ppr_q10", "ppr_q90", "std_q10", "std_q90"})

    def test_api_returns_range_in_the_chosen_scoring_and_a_ppr_label(self):
        ppr = {r["player_id"]: r for r in self.client.get("/api/predictions").json()["results"]}
        std = {r["player_id"]: r for r in self.client.get("/api/predictions", {"scoring": "std"}).json()["results"]}
        for pid, row in ppr.items():
            self.assertLessEqual(row["floor"], row["projected"])
            self.assertGreaterEqual(row["ceiling"], row["projected"])
            self.assertIn(row["consistency"], {"steady", "swingy", "boom_bust"})
            # The numbers follow the scoring switch; the label stays put.
            self.assertEqual(std[pid]["consistency"], row["consistency"])
        p = Prediction.objects.filter(season=2025, week=4).first()
        self.assertEqual(std[p.player_id]["floor"], round(p.floor_std, 1))

    def test_past_weeks_without_a_range_return_nulls(self):
        row = self.client.get("/api/predictions", {"season": 2025, "week": 2}).json()["results"][0]
        self.assertIsNone(row["floor"])
        self.assertIsNone(row["ceiling"])
        self.assertIsNone(row["consistency"])


class RefreshAddsRangesTests(TestCase):
    def test_deploy_retrains_once_when_the_model_has_no_ranges(self):
        populate_db()
        run_pipeline(num_rounds=5)
        run = ModelRun.objects.get()
        run.boosters = {k: v for k, v in run.boosters.items() if k in ("ppr", "std")}
        run.save()
        with (
            mock.patch("predictor.management.commands.refresh.ingest", return_value={}) as ingest,
            mock.patch("predictor.management.commands.refresh.current_season", return_value=2025),
            mock.patch("predictor.modeling.NUM_ROUNDS", 5),
        ):
            call_command("refresh", "--if-empty", stdout=StringIO())
            ingest.assert_called_once_with([2025])
            self.assertIn("ppr_q90", ModelRun.objects.latest().boosters)
            out = StringIO()
            call_command("refresh", "--if-empty", stdout=out)
        self.assertIn("skipping", out.getvalue())
