"""Rating aggregation. Averages are always computed from stored rows —
a client-supplied average is never trusted or persisted."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count

from .models import Review


def published_reviews(product_id: int | None = None):
    qs = Review.objects.filter(is_published=True)
    if product_id is not None:
        qs = qs.filter(product_id=product_id)
    return qs


def product_rating_summary(product_id: int) -> dict:
    qs = published_reviews(product_id)
    aggregate = qs.aggregate(average=Avg("rating"), total=Count("id"))
    distribution = {str(star): 0 for star in range(1, 6)}
    for row in qs.values("rating").annotate(count=Count("id")):
        distribution[str(row["rating"])] = row["count"]

    average = aggregate["average"] or 0
    return {
        "product_id": product_id,
        "average_rating": float(round(Decimal(str(average)), 2)),
        "review_count": aggregate["total"] or 0,
        "distribution": distribution,
    }
