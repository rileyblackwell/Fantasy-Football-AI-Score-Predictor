from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from predictor.modeling import TrainedModels
from predictor.models import ModelRun, Prediction, RefreshLog
from predictor.pipeline import load_latest_models, run_pipeline, target_week
from predictor.tests.factories import populate_db


class PipelineTests(TestCase):
    def setUp(self):
        populate_db()

    def test_target_week_is_first_unplayed_week(self):
        self.assertEqual(target_week(), (2025, 4))

    def test_run_writes_upcoming_and_backtest_predictions(self):
        run = run_pipeline(num_rounds=20)
        self.assertEqual(run.metrics["target_week"], 4)
        self.assertEqual(run.metrics["holdout_season"], 2024)
        self.assertIn("model_mae", run.metrics)
        upcoming = Prediction.objects.filter(season=2025, week=4)
        self.assertEqual(upcoming.count(), 16)  # 4 teams x 4 positions, all play in week 4
        self.assertFalse(upcoming.filter(is_backtest=True).exists())
        self.assertEqual(Prediction.objects.filter(season=2025, is_backtest=True).count(), 16 * 3)
        p = upcoming.first()
        self.assertGreaterEqual(p.points_ppr, 0)
        self.assertAlmostEqual(p.points_half, (p.points_ppr + p.points_std) / 2, places=1)

    def test_model_round_trips_through_database(self):
        run_pipeline(num_rounds=20)
        models = load_latest_models()
        self.assertIsInstance(models, TrainedModels)
        self.assertEqual(set(models.boosters), {"ppr", "std"})

    def test_rerun_replaces_predictions_and_prunes_old_runs(self):
        for _ in range(7):
            run_pipeline(num_rounds=5)
        self.assertEqual(ModelRun.objects.count(), 5)
        self.assertEqual(Prediction.objects.filter(season=2025, week=4).count(), 16)

    def test_inactive_players_are_not_projected(self):
        from predictor.models import Player

        Player.objects.filter(pk="00-AAA-RB").update(roster_status="RES")
        run_pipeline(num_rounds=5)
        self.assertFalse(Prediction.objects.filter(player_id="00-AAA-RB", week=4).exists())


class RefreshCommandTests(TestCase):
    def test_refresh_if_empty_skips_when_model_exists(self):
        populate_db()
        run_pipeline(num_rounds=5)
        out = StringIO()
        with mock.patch("predictor.management.commands.refresh.ingest") as ingest:
            call_command("refresh", "--if-empty", stdout=out)
        ingest.assert_not_called()
        self.assertIn("skipping", out.getvalue())

    def test_refresh_loads_full_history_on_empty_db_and_logs(self):
        def fake_ingest(seasons):
            populate_db()
            return {"stats": 1}

        with (
            mock.patch("predictor.management.commands.refresh.ingest", side_effect=fake_ingest) as ingest,
            mock.patch("predictor.management.commands.refresh.current_season", return_value=2025),
            mock.patch("predictor.modeling.NUM_ROUNDS", 5),
        ):
            call_command("refresh", stdout=StringIO())
        seasons = ingest.call_args.args[0]
        self.assertEqual(seasons[0], 2016)
        self.assertEqual(seasons[-1], 2025)
        log = RefreshLog.objects.get()
        self.assertTrue(log.success)
        self.assertIsNotNone(log.finished_at)

    def test_refresh_failure_is_logged(self):
        with mock.patch("predictor.management.commands.refresh.ingest", side_effect=RuntimeError("nflverse down")):
            with self.assertRaises(Exception):
                call_command("refresh", stdout=StringIO())
        log = RefreshLog.objects.get()
        self.assertFalse(log.success)
        self.assertIn("nflverse down", log.message)


class DeploySetupTests(TestCase):
    def test_deploy_setup_migrates_and_skips_refresh_when_model_exists(self):
        populate_db()
        run_pipeline(num_rounds=5)
        out = StringIO()
        with mock.patch("predictor.management.commands.refresh.ingest") as ingest:
            call_command("deploy_setup", stdout=out)
        ingest.assert_not_called()
        self.assertIn("skipping", out.getvalue())
