import logging
import time
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from predictor.ingest import current_season, ingest
from predictor.models import ModelRun, RefreshLog, WeeklyStat
from predictor.pipeline import run_pipeline

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Scheduled job: pull the latest nflverse data, retrain and write predictions. "
        "Loads all history the first time it runs on an empty database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty", action="store_true", help="Only run when there are no predictions yet (used on deploy)"
        )

    def handle(self, *args, if_empty=False, **options):
        if if_empty and ModelRun.objects.exists():
            self.stdout.write("Data already loaded; skipping refresh.")
            return
        log = RefreshLog.objects.create()
        start = time.perf_counter()
        try:
            latest = current_season()
            if WeeklyStat.objects.exists():
                seasons = [latest]
            else:
                seasons = list(range(settings.FIRST_SEASON, latest + 1))
            summary = ingest(seasons)
            run = run_pipeline()
            log.message = (
                f"Seasons {seasons[0]}-{seasons[-1]}: {summary}. Model run {run.pk} trained on "
                f"{run.training_rows} rows in {run.training_seconds}s. Total {time.perf_counter() - start:.1f}s."
            )
            log.success = True
        except Exception as exc:
            log.message = traceback.format_exc()[-4000:]
            raise CommandError(f"Refresh failed: {exc}") from exc
        finally:
            log.finished_at = timezone.now()
            log.save()
        self.stdout.write(self.style.SUCCESS(log.message))
