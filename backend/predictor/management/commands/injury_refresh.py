import time
import traceback

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from predictor.gameday import refresh_game_day
from predictor.models import RefreshLog


class Command(BaseCommand):
    help = (
        "Game-day job, scheduled hourly: during the hours around this week's kickoffs, pull the latest "
        "injury statuses and re-project players whose games haven't started (no retraining). Outside "
        "those hours it exits at once."
    )

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even outside a game window")

    def handle(self, *args, force=False, **options):
        start = time.perf_counter()
        try:
            summary = refresh_game_day(force=force)
        except Exception as exc:
            RefreshLog.objects.create(message="Game-day injury check failed:\n" + traceback.format_exc()[-4000:],
                                      finished_at=timezone.now())
            raise CommandError(f"Game-day injury check failed: {exc}") from exc
        if not summary["ran"]:
            self.stdout.write(f"Skipped: {summary['reason']}.")
            return
        out = summary["newly_out"]
        message = (
            f"Game-day injury check, {summary['season']} week {summary['week']}: "
            f"{len(summary['changed'])} status changes, {len(out)} newly Out"
            f"{' (' + ', '.join(out[:10]) + ')' if out else ''}, {summary['reprojected']} players re-projected. "
            f"{time.perf_counter() - start:.1f}s."
        )
        RefreshLog.objects.create(message=message, success=True, finished_at=timezone.now())
        self.stdout.write(self.style.SUCCESS(message))
