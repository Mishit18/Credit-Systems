"""
Trigger Celery task to ingest customer and loan data from Excel.
Usage: python manage.py trigger_ingestion
"""
from django.core.management.base import BaseCommand
from core.tasks import ingest_customer_and_loan_data


class Command(BaseCommand):
    help = "Trigger background ingestion of customer_data.xlsx and loan_data.xlsx"

    def add_arguments(self, parser):
        parser.add_argument("--sync", action="store_true", help="Run ingestion synchronously (no Celery)")

    def handle(self, *args, **options):
        if options["sync"]:
            result = ingest_customer_and_loan_data()
            self.stdout.write(self.style.SUCCESS(f"Sync ingestion result: {result}"))
        else:
            task = ingest_customer_and_loan_data.delay()
            self.stdout.write(self.style.SUCCESS(f"Ingestion task queued: {task.id}"))
