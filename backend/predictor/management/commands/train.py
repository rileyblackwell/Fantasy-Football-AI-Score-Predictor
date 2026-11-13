from django.core.management.base import BaseCommand

from predictor.pipeline import run_pipeline


class Command(BaseCommand):
    help = "Train the LightGBM models and write predictions for the upcoming week."

    def add_arguments(self, parser):
        parser.add_argument("--rounds", type=int, default=None, help="Boosting rounds (default from modeling.py)")

    def handle(self, *args, rounds=None, **options):
        run = run_pipeline(num_rounds=rounds)
        self.stdout.write(
            self.style.SUCCESS(
                f"Model run {run.pk}: {run.training_rows} rows in {run.training_seconds}s, metrics={run.metrics}"
            )
        )
