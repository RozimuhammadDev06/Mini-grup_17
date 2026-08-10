"""
Product comparison and wishlist logic.

Comparison is persisted (the ERD's ``Compare`` model) so a guest's selection
survives a page reload, and is scoped to one category at a time because
comparing a drill against cement has no meaningful shared attributes.
"""

from __future__ import annotations

from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from apps.catalog.models import Product

from .models import Compare, Wishlist

MAX_COMPARE_PRODUCTS = 4
MIN_COMPARE_PRODUCTS = 2


def _owner_filter(request) -> dict:
    """Rows belong to a user, or to an anonymous session — never both."""
    if request.user.is_authenticated:
        return {"user": request.user}
    if not request.session.session_key:
        request.session.save()
    return {"user": None, "session_key": request.session.session_key}


def compare_queryset(request) -> QuerySet[Compare]:
    return (Compare.objects
            .filter(**_owner_filter(request))
            .select_related("product", "category"))


def add_to_compare(request, product: Product) -> Compare:
    owner = _owner_filter(request)
    existing = Compare.objects.filter(**owner)

    if existing.filter(product=product).exists():
        raise ValidationError(
            {"product_id": ["This product is already in the comparison."]})

    current_category = existing.values_list("category_id", flat=True).first()
    if current_category and current_category != product.category_id:
        raise ValidationError({"product_id": [
            "Products from a different category cannot be compared. "
            "Clear the comparison first."]})

    if existing.count() >= MAX_COMPARE_PRODUCTS:
        raise ValidationError({"product_id": [
            f"You can compare at most {MAX_COMPARE_PRODUCTS} products."]})

    return Compare.objects.create(
        product=product, category=product.category, **owner)


def remove_from_compare(request, product: Product) -> None:
    deleted, _ = Compare.objects.filter(
        **_owner_filter(request), product=product).delete()
    if not deleted:
        raise ValidationError(
            {"detail": ["This product is not in the comparison."]})


def clear_compare(request) -> None:
    Compare.objects.filter(**_owner_filter(request)).delete()


def validate_comparison_ids(product_ids: list[int]) -> list[int]:
    """Validate an ad-hoc comparison request that persists nothing."""
    if len(product_ids) != len(set(product_ids)):
        raise ValidationError(
            {"product_ids": ["Duplicate product ids are not allowed."]})
    if len(product_ids) < MIN_COMPARE_PRODUCTS:
        raise ValidationError({"product_ids": [
            f"Provide at least {MIN_COMPARE_PRODUCTS} products to compare."]})
    if len(product_ids) > MAX_COMPARE_PRODUCTS:
        raise ValidationError({"product_ids": [
            f"You can compare at most {MAX_COMPARE_PRODUCTS} products."]})
    return product_ids


def comparison_matrix(products: list[Product]) -> list[dict]:
    """
    Build the attribute rows shared by the compared products.

    Every attribute present on any product becomes a row; products missing it
    get ``None``, which lets the frontend render a stable table.
    """
    rows: dict[int, dict] = {}
    for product in products:
        for pa in product.product_attributes.all():
            row = rows.setdefault(pa.attribute_id, {
                "attribute_id": pa.attribute_id,
                "code": pa.attribute.code,
                "name": pa.attribute.name,
                "unit": pa.attribute.unit,
                "values": {},
            })
            if pa.value_number is not None:
                row["values"][product.id] = str(pa.value_number)
            elif pa.value is not None:
                row["values"][product.id] = (
                    pa.value.value_string or str(pa.value.value_number))

    result = []
    for row in rows.values():
        row["values"] = {p.id: row["values"].get(p.id) for p in products}
        row["is_common"] = all(v is not None for v in row["values"].values())
        result.append(row)
    # Attributes shared by every product are the useful ones — show them first.
    result.sort(key=lambda r: (not r["is_common"], r["name"]))
    return result


# --------------------------------------------------------------------------
# Wishlist
# --------------------------------------------------------------------------

def wishlist_queryset(user) -> QuerySet[Wishlist]:
    return (Wishlist.objects
            .filter(user=user)
            .select_related("product", "product__brand", "product__category",
                            "product__stock")
            .prefetch_related("product__images"))


def add_to_wishlist(user, product: Product) -> Wishlist:
    item, created = Wishlist.objects.get_or_create(user=user, product=product)
    if not created:
        raise ValidationError(
            {"product_id": ["This product is already in your wishlist."]})
    return item


def remove_from_wishlist(user, product: Product) -> None:
    deleted, _ = Wishlist.objects.filter(user=user, product=product).delete()
    if not deleted:
        raise ValidationError(
            {"detail": ["This product is not in your wishlist."]})


def is_in_wishlist(user, product_id: int) -> bool:
    if not user.is_authenticated:
        return False
    return Wishlist.objects.filter(user=user, product_id=product_id).exists()
