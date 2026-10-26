import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from market.models import Campaign
from market.services import settle_campaign


class Command(BaseCommand):
    help = "Idempotently settle all due, published campaigns. Run every minute."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true", help="Poll until interrupted.")
        parser.add_argument("--interval", type=int, default=30, help="Polling seconds (minimum 1).")

    def settle_due(self) -> None:
        ids = Campaign.objects.filter(
            status__in=["active", "funded"], deadline__lte=timezone.now()
        ).values_list("pk", flat=True)
        count = sum(settle_campaign(pk) for pk in ids.iterator())
        self.stdout.write(self.style.SUCCESS(f"Settled {count} campaign(s)."))

    def handle(self, *args, **options):
        try:
            while True:
                self.settle_due()
                if not options["watch"]:
                    break
                time.sleep(max(1, options["interval"]))
        except KeyboardInterrupt:
            self.stdout.write("Deadline worker stopped.")
