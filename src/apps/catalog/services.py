"""
Inventory mutations.

``Stock.quantity`` is the single source of truth for what can be sold, and
every runtime change to it goes through this module so the same guarantees
hold on every database backend:

* rows are locked in product order (``select_for_update``) before they are
  read for validation, so concurrent checkouts queue instead of deadlocking;
* the decrement is conditional (``quantity >= n``), so even where row locks
  are unavailable (SQLite) a sale can never take stock below zero — the
  losing transaction gets a validation error and rolls back;
* the ``CHECK (quantity >= 0)`` constraint is the last line of defence.

Callers own the surrounding transaction: these helpers must run inside
``transaction.atomic`` together with the order changes they belong to.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .models import Stock


def lock_stock(product_ids: Iterable[int]) -> dict[int, Stock]:
    """Lock and return the stock rows of ``product_ids``, keyed by product."""
    ids = sorted({pid for pid in product_ids if pid is not None})
    return {
        stock.product_id: stock
        for stock in Stock.objects.select_for_update()
        .filter(product_id__in=ids).order_by("product_id")
    }


def deduct_stock(quantities: Mapping[int, int], *,
                 names: Optional[Mapping[int, str]] = None) -> None:
    """
    Take ``quantities`` ({product_id: units}) out of stock, all or nothing.

    Raises ``ValidationError`` when any line is no longer covered; the
    caller's transaction then rolls back every decrement made so far.
    """
    names = names or {}
    for product_id, units in sorted(quantities.items()):
        if units <= 0:
            continue
        updated = (Stock.objects
                   .filter(product_id=product_id, quantity__gte=units)
                   .update(quantity=F("quantity") - units))
        if not updated:
            name = names.get(product_id, f"#{product_id}")
            raise ValidationError({"detail": [
                f"'{name}' no longer has {units} unit(s) in stock. "
                f"Please review your cart."]})
    _after_stock_change(quantities)


def return_stock(quantities: Mapping[int, int]) -> None:
    """Put ``quantities`` ({product_id: units}) back on the shelf."""
    for product_id, units in sorted(
            (pid, units) for pid, units in quantities.items()
            if pid is not None):
        if units <= 0:
            continue
        # The row can only be missing if it was deleted after the sale; the
        # units still physically come back, so recreate it rather than lose
        # them.
        stock, _ = (Stock.objects.select_for_update()
                    .get_or_create(product_id=product_id))
        Stock.objects.filter(pk=stock.pk).update(
            quantity=F("quantity") + units)
    _after_stock_change(quantities)


def refresh_stock_statuses(product_ids: Iterable[int]) -> bool:
    """
    Re-derive ``Stock.status`` after quantity-only updates.

    Returns True when any status changed (availability or the low-stock
    badge), which is what cached catalogue pages display.
    """
    changed = False
    for stock in Stock.objects.filter(product_id__in=list(product_ids)):
        status = Stock.status_for(stock.quantity, stock.status)
        if stock.status != status:
            Stock.objects.filter(pk=stock.pk).update(status=status)
            changed = True
    return changed


def _after_stock_change(quantities: Mapping[int, int]) -> None:
    if refresh_stock_statuses(pid for pid in quantities if pid is not None):
        from apps.content.selectors import invalidate_home_cache
        # After commit: invalidating earlier would let a concurrent request
        # re-cache the pre-commit figures until the TTL expires.
        transaction.on_commit(invalidate_home_cache, robust=True)
