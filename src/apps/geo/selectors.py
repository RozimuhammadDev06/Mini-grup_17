"""Read-side queries for delivery geography."""

from __future__ import annotations

from django.db.models import QuerySet

from .models import City


def deliverable_cities() -> QuerySet[City]:
    """
    Cities that belong to a delivery zone — the only ones checkout delivers
    to, because the zone is what prices the delivery.
    """
    return (City.objects
            .filter(delivery_zone__isnull=False)
            .select_related("region", "delivery_zone")
            .order_by("region__name", "name"))
