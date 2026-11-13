from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pre-deploy step: apply migrations, then load data and train if the database has no model yet."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, stdout=self.stdout)
        call_command("refresh", if_empty=True, stdout=self.stdout)
