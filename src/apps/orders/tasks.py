"""Periodic order housekeeping, scheduled in ``CELERY_BEAT_SCHEDULE``."""

from celery import shared_task

from . import services


@shared_task(name="orders.release_expired_orders")
def release_expired_orders() -> int:
    """Cancel card orders left unpaid too long and return their stock."""
    return len(services.release_expired_orders())
