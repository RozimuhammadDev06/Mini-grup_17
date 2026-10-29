"""
Order creation and status transitions.

Checkout runs inside one transaction and locks every ``Stock`` row it touches
with ``select_for_update``, so two customers racing for the last unit cannot
both succeed. Product name, article and price are snapshotted onto the order
line, so a later price import never rewrites history.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, QuerySet
from django.utils import timezone

from apps.carts import services as cart_services
from apps.carts.models import Cart
from apps.carts.sessions import guest_session_key
from apps.catalog.models import Stock
from apps.discounts.services import PricingService, money

from .models import Order, OrderItem

logger = logging.getLogger(__name__)

# Transitions the API is allowed to perform. Payment webhooks and staff tools
# drive the rest of the state machine.
CUSTOMER_CANCELLABLE = {
    Order.Status.NEW,
    Order.Status.AWAITING_PAYMENT,
    Order.Status.PROCESSING,
}

# A card order in these statuses is still waiting for its online payment
# while holding stock — the orders the unpaid-order expiry applies to.
UNPAID_STATUSES = (Order.Status.NEW, Order.Status.AWAITING_PAYMENT)


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


def owned_orders(request) -> QuerySet[Order]:
    """
    The orders this request may see: a signed-in user's, or those placed
    from the caller's guest session.

    A visitor without a valid session owns nothing. Filtering on a missing
    key would otherwise match every order that has no owner at all.
    """
    if request.user.is_authenticated:
        return order_queryset(request.user)
    key = guest_session_key(request, create=False)
    if not key:
        return Order.objects.none()
    return (Order.objects
            .filter(user__isnull=True, session_key=key)
            .prefetch_related("items", "items__product", "payments"))


def _delivery_city(delivery_type: str, city_id: Optional[int]):
    """
    The city a delivery goes to, or ``None`` for pickup.

    The city prices the delivery, so it is required and must belong to a
    delivery zone. A missing or unknown city used to price delivery at zero;
    a city the store should deliver to for free needs a zone costing 0.
    """
    if delivery_type == Order.DeliveryType.PICKUP:
        return None
    from apps.geo.selectors import deliverable_cities
    city = deliverable_cities().filter(pk=city_id).first() if city_id else None
    if city is None:
        raise ValidationError(
            {"city_id": ["Choose a city we deliver to."]})
    return city


@transaction.atomic
def create_order_from_cart(
    *,
    user=None,
    session_key: Optional[str] = None,
    cart: Cart,
    address_snapshot: dict,
    customer: Optional[dict] = None,
    delivery_type: str = Order.DeliveryType.DELIVERY,
    payment_method: str = Order.PaymentMethod.CARD,
    city_id: Optional[int] = None,
) -> Order:
    """
    Place an order owned by ``user``, or by the guest ``session_key``.

    ``customer`` holds the contact details (``name``, ``phone``, ``email``)
    staff need to reach a guest, who has no profile to look them up in.
    """
    if user is None and not session_key:
        raise ValueError("An order needs a user or a guest session key.")
    customer = customer or {}

    items = list(cart.items.select_related("product"))
    if not items:
        raise ValidationError({"detail": ["Your cart is empty."]})

    city = _delivery_city(delivery_type, city_id)
    if city is not None:
        # The chosen city is what was priced, so it is also where the order
        # goes: the address cannot name a different one.
        address_snapshot = {**address_snapshot, "city": city.name,
                            "region": city.region.name}

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
        delivery_cost=(city.delivery_zone.base_cost if city is not None
                       else Decimal("0.00")),
    )

    order = Order.objects.create(
        number=generate_order_number(),
        user=user,
        session_key=None if user is not None else session_key,
        customer_name=customer.get("name", ""),
        customer_phone=customer.get("phone", ""),
        customer_email=customer.get("email", ""),
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


def payment_due_at(order: Order) -> Optional[datetime]:
    """When an unpaid card order will be released, or ``None``."""
    if (order.payment_method != Order.PaymentMethod.CARD
            or order.paid_at is not None
            or order.status not in UNPAID_STATUSES):
        return None
    return order.created_at + timedelta(
        minutes=settings.UNPAID_ORDER_TTL_MINUTES)


def release_expired_orders(*, now: Optional[datetime] = None) -> list[str]:
    """
    Cancel card orders left unpaid past ``UNPAID_ORDER_TTL_MINUTES`` and
    return their stock. Returns the numbers of the released orders.

    Each order is re-read under a row lock, the same lock the payment
    callbacks take, so an order paid while this runs is left alone; once
    released, the callbacks refuse to take payment for it.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=settings.UNPAID_ORDER_TTL_MINUTES)
    unpaid = dict(payment_method=Order.PaymentMethod.CARD,
                  status__in=UNPAID_STATUSES, paid_at__isnull=True)
    candidates = list(Order.objects.filter(created_at__lt=cutoff, **unpaid)
                      .values_list("pk", flat=True))

    released = []
    for pk in candidates:
        with transaction.atomic():
            order = (Order.objects.select_for_update()
                     .filter(pk=pk, **unpaid).first())
            if order is None:  # paid or cancelled in the meantime
                continue
            restock_order(order)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
        released.append(order.number)
        logger.info("Released unpaid order %s after %s minutes",
                    order.number, settings.UNPAID_ORDER_TTL_MINUTES)
    return released


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
