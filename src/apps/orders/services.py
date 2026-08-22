"""
Order creation and status transitions.

Checkout runs inside one transaction and locks every ``Stock`` row it touches
with ``select_for_update``, so two customers racing for the last unit cannot
both succeed. Product name, article and price are snapshotted onto the order
line, so a later price import never rewrites history.
"""

from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Iterable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, QuerySet
from django.utils import timezone

from apps.carts import services as cart_services
from apps.carts.models import Cart
from apps.catalog.models import Stock
from apps.discounts.services import PricingService, money

from .models import Order, OrderItem

# Transitions the API is allowed to perform. Payment webhooks and staff tools
# drive the rest of the state machine.
CUSTOMER_CANCELLABLE = {
    Order.Status.NEW,
    Order.Status.AWAITING_PAYMENT,
    Order.Status.PROCESSING,
}


def generate_order_number() -> str:
    """Human-quotable, non-sequential (a sequence would leak order volume)."""
    stamp = timezone.now().strftime("%y%m%d")
    for _ in range(10):
        number = f"{stamp}-{secrets.randbelow(10 ** 6):06d}"
        if not Order.objects.filter(number=number).exists():
            return number
    raise RuntimeError("Could not allocate a unique order number.")


def order_queryset(user) -> QuerySet[Order]:
    """Every order query for a customer starts here — never a bare filter."""
    return (Order.objects
            .filter(user=user)
            .prefetch_related("items", "items__product", "payments"))


def _delivery_cost(delivery_type: str, city_id: Optional[int]) -> Decimal:
    """Zone-based delivery cost; pickup is always free."""
    if delivery_type == Order.DeliveryType.PICKUP or not city_id:
        return Decimal("0.00")
    from apps.geo.models import City
    city = (City.objects
            .select_related("delivery_zone")
            .filter(pk=city_id)
            .first())
    if city is None or city.delivery_zone is None:
        return Decimal("0.00")
    return money(city.delivery_zone.base_cost)


@transaction.atomic
def create_order_from_cart(
    *,
    user,
    cart: Cart,
    address_snapshot: dict,
    delivery_type: str = Order.DeliveryType.DELIVERY,
    payment_method: str = Order.PaymentMethod.CARD,
    city_id: Optional[int] = None,
) -> Order:
    items = list(cart.items.select_related("product"))
    if not items:
        raise ValidationError({"detail": ["Your cart is empty."]})

    # Lock stock rows in a deterministic order to avoid deadlocks between
    # two concurrent checkouts that share products.
    product_ids = sorted(item.product_id for item in items)
    stocks = {
        stock.product_id: stock
        for stock in Stock.objects.select_for_update()
        .filter(product_id__in=product_ids)
    }

    subtotal = Decimal("0.00")
    for item in items:
        stock = stocks.get(item.product_id)
        on_hand = stock.quantity if stock else 0
        if item.quantity > on_hand:
            raise ValidationError({"detail": [
                f"Only {on_hand} unit(s) of '{item.product.name}' are in "
                f"stock."]})
        # Re-read the price from the catalogue: the cart may be hours old.
        subtotal += money(item.product.price) * item.quantity

    breakdown = PricingService.breakdown(
        subtotal=subtotal,
        promo_code=cart.promo_code,
        delivery_cost=_delivery_cost(delivery_type, city_id),
    )

    order = Order.objects.create(
        number=generate_order_number(),
        user=user,
        status=(Order.Status.AWAITING_PAYMENT
                if payment_method == Order.PaymentMethod.CARD
                else Order.Status.PROCESSING),
        delivery_type=delivery_type,
        address_snapshot=address_snapshot,
        payment_method=payment_method,
        subtotal=breakdown.subtotal,
        cart_discount=breakdown.tier_discount,
        promo_discount=breakdown.promo_discount,
        delivery_cost=breakdown.delivery_cost,
        total=breakdown.total,
    )

    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=item.product,
            name_snapshot=item.product.name,
            article_snapshot=item.product.article,
            price=money(item.product.price),
            quantity=item.quantity,
        )
        for item in items
    ])

    for item in items:
        Stock.objects.filter(product_id=item.product_id).update(
            quantity=F("quantity") - item.quantity)
    _refresh_stock_statuses(product_ids)

    if breakdown.promo_code is not None:
        type(breakdown.promo_code).objects.filter(
            pk=breakdown.promo_code.pk).update(used_count=F("used_count") + 1)

    cart_services.clear(cart)
    return order


def _refresh_stock_statuses(product_ids: Iterable[int]) -> None:
    for stock in Stock.objects.filter(product_id__in=list(product_ids)):
        if stock.quantity <= 0:
            status = Stock.Status.OUT_OF_STOCK
        elif stock.quantity <= 5:
            status = Stock.Status.LOW_STOCK
        else:
            status = Stock.Status.IN_STOCK
        if stock.status != status:
            stock.status = status
            stock.save(update_fields=["status"])


def restock_order(order: Order) -> None:
    """Return an order's reserved stock. Used by cancellation and refunds."""
    product_ids = []
    for item in order.items.select_related("product"):
        if item.product_id:
            Stock.objects.filter(product_id=item.product_id).update(
                quantity=F("quantity") + item.quantity)
            product_ids.append(item.product_id)
    _refresh_stock_statuses(product_ids)


@transaction.atomic
def cancel_order(order: Order) -> Order:
    """Customer-initiated cancellation; returns the reserved stock."""
    if order.status not in CUSTOMER_CANCELLABLE:
        raise ValidationError({"detail": [
            f"An order in status '{order.get_status_display()}' can no longer "
            f"be cancelled."]})

    restock_order(order)
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return order


def has_purchased(user, product_id: int) -> bool:
    """Used to gate product reviews to verified buyers."""
    return OrderItem.objects.filter(
        order__user=user,
        product_id=product_id,
        order__status__in=(
            Order.Status.PROCESSING, Order.Status.ASSEMBLED,
            Order.Status.SHIPPED, Order.Status.READY_FOR_PICKUP,
            Order.Status.COMPLETED),
    ).exists()
