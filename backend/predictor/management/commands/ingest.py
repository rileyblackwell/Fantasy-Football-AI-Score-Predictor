from django.conf import settings
from django.core.management.base import BaseCommand

from predictor.ingest import current_season, ingest


class Command(BaseCommand):
    help = "Download nflverse stats, schedules, rosters and injuries into the database."

    def add_arguments(self, parser):
        parser.add_argument("--seasons", nargs="+", type=int, help="Seasons to load (default: current season)")
        parser.add_argument("--full", action="store_true", help="Load every season from FIRST_SEASON onward")

    def handle(self, *args, seasons=None, full=False, **options):
        latest = current_season()
        if full:
            seasons = list(range(settings.FIRST_SEASON, latest + 1))
        seasons = seasons or [latest]
        summary = ingest(seasons)
        self.stdout.write(self.style.SUCCESS(f"Ingested {seasons}: {summary}"))
