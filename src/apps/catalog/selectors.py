"""
Read-side query builders for the catalog.

Aggregates are computed with correlated subqueries rather than joined
annotations: a product joined to both its reviews and its order items would
multiply rows and silently corrupt every ``Sum``/``Avg`` in the same query.
"""

from __future__ import annotations

from typing import Iterable

from django.db.models import (Avg, Count, DecimalField, F, Func, IntegerField,
                              OuterRef, Prefetch, Q, QuerySet, Subquery, Sum)
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


# ---------------------------------------------------------------------------
# Category membership and product counts
# ---------------------------------------------------------------------------
# A category "contains" the active products assigned to it or to one of its
# direct subcategories (the storefront tree is two levels deep). That is the
# set ``GET /catalog/products/?category=<id>`` returns, and ``product_count``
# counts exactly that set everywhere it is shown: category list, detail and
# tree, the category nested in every product, and the home page.

def category_products_q(category_ids: Iterable[int]) -> Q:
    """Products that belong to any of ``category_ids`` (subcategories too)."""
    ids = list(category_ids)
    return Q(category_id__in=ids) | Q(category__parent_id__in=ids)


def category_slug_products_q(slug: str) -> Q:
    """``category_products_q`` addressed by slug (case-insensitive)."""
    return (Q(category__slug__iexact=slug)
            | Q(category__parent__slug__iexact=slug))


def product_count_expression():
    """Annotation expression: visible products in a category's subtree."""
    return Coalesce(
        Subquery(
            Product.objects
            .filter(is_active=True)
            .filter(Q(category_id=OuterRef("pk"))
                    | Q(category__parent_id=OuterRef("pk")))
            .order_by()
            .annotate(count=Func(F("pk"), function="COUNT",
                                 output_field=IntegerField()))
            .values("count")[:1]
        ),
        0,
        output_field=IntegerField(),
    )


def with_product_count(queryset: QuerySet[Category]) -> QuerySet[Category]:
    return queryset.annotate(product_count=product_count_expression())


def count_products_in_category(category: Category) -> int:
    """Same rule as ``product_count_expression`` for one, unannotated row."""
    return (Product.objects.filter(is_active=True)
            .filter(category_products_q([category.pk])).count())


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------
# ``Stock.quantity`` is authoritative; a product without a stock row has no
# units. Cart validation and checkout apply the same rule in
# ``apps.carts.services`` and ``apps.catalog.services``.

def in_stock_filter() -> Q:
    return Q(stock__quantity__gt=0)


def out_of_stock_filter() -> Q:
    return Q(stock__isnull=True) | Q(stock__quantity__lte=0)


def available_quantity(product: Product) -> int:
    """Units of ``product`` that can be sold right now (0 without a row)."""
    stock = getattr(product, "stock", None)
    return max(stock.quantity, 0) if stock is not None else 0


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def product_queryset(*, only_active: bool = True) -> QuerySet[Product]:
    """
    List queryset: joins, prefetches and rating/stock/sales annotations.

    Every endpoint that renders a product card (catalogue, home, cart,
    wishlist, comparison) builds on this, so the card's figures cannot
    differ between endpoints. The category is prefetched with its
    ``product_count`` (one extra query per page, not per product).
    """
    qs = Product.objects.select_related("brand", "stock")
    if only_active:
        qs = qs.filter(is_active=True)
    return qs.prefetch_related(
        "images",
        Prefetch("category",
                 queryset=with_product_count(Category.objects.all())),
    ).annotate(
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
    """Active categories annotated with ``product_count`` (see above)."""
    return with_product_count(
        Category.objects.filter(is_active=True).select_related("parent"))
