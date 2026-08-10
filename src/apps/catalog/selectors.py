"""
Read-side query builders for the catalog.

Aggregates are computed with correlated subqueries rather than joined
annotations: a product joined to both its reviews and its order items would
multiply rows and silently corrupt every ``Sum``/``Avg`` in the same query.
"""

from __future__ import annotations

from django.db.models import (Avg, Count, DecimalField, F, IntegerField,
                              OuterRef, Q, QuerySet, Subquery, Sum)
from django.db.models.functions import Coalesce

from .models import Category, Product

# Statuses that count as a real sale for "best selling" ranking.
SOLD_STATUSES = (
    "processing", "assembled", "shipped", "ready_for_pickup", "completed",
)


def _review_subquery(aggregate):
    from apps.reviews.models import Review
    return Subquery(
        Review.objects
        .filter(product=OuterRef("pk"), is_published=True)
        .values("product")
        .annotate(value=aggregate)
        .values("value")[:1]
    )


def _sold_subquery():
    from apps.orders.models import OrderItem
    return Subquery(
        OrderItem.objects
        .filter(product=OuterRef("pk"), order__status__in=SOLD_STATUSES)
        .values("product")
        .annotate(value=Sum("quantity"))
        .values("value")[:1]
    )


def product_queryset(*, only_active: bool = True) -> QuerySet[Product]:
    """List queryset: joins, prefetches and rating/stock/sales annotations."""
    qs = Product.objects.select_related("category", "brand", "stock")
    if only_active:
        qs = qs.filter(is_active=True)
    return qs.prefetch_related("images").annotate(
        rating=Coalesce(
            _review_subquery(Avg("rating")),
            0.0,
            output_field=DecimalField(max_digits=3, decimal_places=2),
        ),
        review_count=Coalesce(
            _review_subquery(Count("id")), 0, output_field=IntegerField()),
        sold_count=Coalesce(
            _sold_subquery(), 0, output_field=IntegerField()),
        stock_quantity=Coalesce(
            F("stock__quantity"), 0, output_field=IntegerField()),
    )


def product_detail_queryset() -> QuerySet[Product]:
    """Detail queryset: everything the list needs plus attribute rows."""
    return product_queryset().prefetch_related(
        "product_attributes__attribute",
        "product_attributes__value",
    )


def related_products(product: Product, limit: int = 8) -> QuerySet[Product]:
    """Same category, cheapest price distance first, excluding the product."""
    return (product_queryset()
            .filter(category_id=product.category_id)
            .exclude(pk=product.pk)[:limit])


def category_queryset() -> QuerySet[Category]:
    """Active categories annotated with how many active products they hold."""
    return (Category.objects
            .filter(is_active=True)
            .select_related("parent")
            .annotate(product_count=Count(
                "products", filter=Q(products__is_active=True), distinct=True)))


def in_stock_filter() -> Q:
    return Q(stock__quantity__gt=0)
