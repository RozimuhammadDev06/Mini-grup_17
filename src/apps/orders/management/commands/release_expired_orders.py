"""
Cancel card orders left unpaid past ``UNPAID_ORDER_TTL_MINUTES``.

Celery beat runs the same job every five minutes. This command is for
deployments without beat (schedule it with cron) and for running it by hand.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.orders import services


class Command(BaseCommand):
    help = ("Cancel card orders left unpaid longer than "
            "UNPAID_ORDER_TTL_MINUTES and return their stock.")

    def handle(self, *args, **options):
        released = services.release_expired_orders()
        if released:
            self.stdout.write(self.style.SUCCESS(
                f"Released {len(released)} unpaid order(s): "
                f"{', '.join(released)}"))
        else:
            self.stdout.write(
                f"No card orders unpaid for more than "
                f"{settings.UNPAID_ORDER_TTL_MINUTES} minutes.")
