"""
Cart business logic.

Prices always come from the database — a quantity is the only thing a client
is allowed to influence. Guests are identified by the Django session key so
checkout works before registration, and their cart is merged into the account
cart on login.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from apps.catalog.models import Product
from apps.discounts.models import PromoCode
from apps.discounts.services import (PriceBreakdown, PricingService,
                                     PromoCodeError, money)

from .models import Cart, CartItem

MAX_QUANTITY_PER_ITEM = 999


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def resolve_cart(request, *, create: bool = True) -> Optional[Cart]:
    """Return the cart for this request, creating it on demand."""
    if request.user.is_authenticated:
        if create:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        return Cart.objects.filter(user=request.user).first()

    key = _session_key(request)
    cart = Cart.objects.filter(session_key=key, user__isnull=True).first()
    if cart is None and create:
        cart = Cart.objects.create(session_key=key)
    return cart


def cart_items(cart: Cart) -> QuerySet[CartItem]:
    return (cart.items
            .select_related("product", "product__stock", "product__brand",
                            "product__category")
            .prefetch_related("product__images"))


def available_stock(product: Product) -> int:
    stock = getattr(product, "stock", None)
    return stock.quantity if stock else 0


def _validate_stock(product: Product, quantity: int) -> None:
    if quantity < 1:
        raise ValidationError({"quantity": ["Quantity must be at least 1."]})
    if quantity > MAX_QUANTITY_PER_ITEM:
        raise ValidationError(
            {"quantity": [f"Maximum {MAX_QUANTITY_PER_ITEM} per item."]})
    on_hand = available_stock(product)
    if quantity > on_hand:
        raise ValidationError({"quantity": [
            f"Only {on_hand} unit(s) of '{product.name}' are in stock."]})


@transaction.atomic
def add_item(cart: Cart, product: Product, quantity: int = 1) -> CartItem:
    """Add to the existing line rather than replacing it."""
    item = cart.items.filter(product=product).first()
    new_quantity = (item.quantity if item else 0) + quantity
    _validate_stock(product, new_quantity)

    if item is None:
        item = CartItem.objects.create(
            cart=cart, product=product, quantity=new_quantity,
            price=product.price)
    else:
        item.quantity = new_quantity
        item.price = product.price  # re-price to the current catalogue price
        item.save(update_fields=["quantity", "price"])
    cart.save(update_fields=["updated_at"])
    return item


@transaction.atomic
def set_quantity(cart: Cart, product: Product, quantity: int) -> Optional[CartItem]:
    """Set an absolute quantity; 0 removes the line."""
    if quantity == 0:
        remove_item(cart, product)
        return None
    _validate_stock(product, quantity)
    item, _ = CartItem.objects.update_or_create(
        cart=cart, product=product,
        defaults={"quantity": quantity, "price": product.price})
    cart.save(update_fields=["updated_at"])
    return item


def remove_item(cart: Cart, product: Product) -> None:
    deleted, _ = cart.items.filter(product=product).delete()
    if not deleted:
        raise ValidationError({"detail": ["This product is not in the cart."]})
    cart.save(update_fields=["updated_at"])


def clear(cart: Cart) -> None:
    cart.items.all().delete()
    cart.promo_code = None
    cart.save(update_fields=["promo_code", "updated_at"])


def subtotal(cart: Cart) -> Decimal:
    return money(sum(
        (item.price * item.quantity for item in cart.items.all()), Decimal("0")))


def price_breakdown(cart: Cart, delivery_cost=Decimal("0")) -> PriceBreakdown:
    return PricingService.breakdown(
        subtotal=subtotal(cart),
        promo_code=cart.promo_code,
        delivery_cost=delivery_cost,
    )


def apply_promo_code(cart: Cart, code: str) -> PromoCode:
    promo = PromoCode.objects.filter(code__iexact=code.strip()).first()
    if promo is None:
        raise ValidationError({"code": ["Invalid promo code."]})
    try:
        PricingService.validate_promo_code(promo, subtotal(cart))
    except PromoCodeError as exc:
        raise ValidationError({"code": [str(exc)]}) from exc
    cart.promo_code = promo
    cart.save(update_fields=["promo_code", "updated_at"])
    return promo


def remove_promo_code(cart: Cart) -> None:
    cart.promo_code = None
    cart.save(update_fields=["promo_code", "updated_at"])


@transaction.atomic
def merge_guest_cart(request, user) -> Optional[Cart]:
    """
    Fold the anonymous session cart into the user's cart at login.

    Quantities are summed and then clamped to available stock, so merging can
    never create an unfulfillable line.
    """
    key = request.session.session_key
    if not key:
        return None
    guest_cart = Cart.objects.filter(
        session_key=key, user__isnull=True).first()
    if guest_cart is None:
        return None

    user_cart, _ = Cart.objects.get_or_create(user=user)
    for guest_item in guest_cart.items.select_related("product", "product__stock"):
        existing = user_cart.items.filter(product=guest_item.product).first()
        wanted = (existing.quantity if existing else 0) + guest_item.quantity
        wanted = min(wanted, available_stock(guest_item.product))
        if wanted < 1:
            continue
        CartItem.objects.update_or_create(
            cart=user_cart, product=guest_item.product,
            defaults={"quantity": wanted, "price": guest_item.product.price})

    if user_cart.promo_code is None and guest_cart.promo_code is not None:
        user_cart.promo_code = guest_cart.promo_code
        user_cart.save(update_fields=["promo_code"])

    guest_cart.delete()
    return user_cart
