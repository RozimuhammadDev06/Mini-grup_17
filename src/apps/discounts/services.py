"""
The single source of truth for money arithmetic.

Cart totals, order totals and any price preview must go through
:class:`PricingService` so a customer never sees one number in the cart and a
different one on the order.

Discounts stack in a fixed order:

1. ``DiscountTier`` — a volume discount driven by the cart subtotal.
2. ``PromoCode`` — applied to what is left after the tier discount, so the two
   mechanics cannot combine into more than 100% off.
3. Delivery cost is added last and is never discounted.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.utils import timezone

from .models import DiscountTier, PromoCode

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    """Coerce anything numeric to a 2-decimal ``Decimal``, rounding half up."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceBreakdown:
    subtotal: Decimal
    tier_discount: Decimal
    promo_discount: Decimal
    delivery_cost: Decimal
    total: Decimal
    tier: Optional[DiscountTier] = None
    promo_code: Optional[PromoCode] = None

    @property
    def discount_total(self) -> Decimal:
        return money(self.tier_discount + self.promo_discount)


class PromoCodeError(ValueError):
    """A promo code was supplied but cannot be used for this subtotal."""


class PricingService:
    @staticmethod
    def active_tier(subtotal: Decimal) -> Optional[DiscountTier]:
        """Highest active tier whose threshold the subtotal reaches."""
        return (DiscountTier.objects
                .filter(is_active=True, threshold__lte=subtotal)
                .order_by("-threshold")
                .first())

    @staticmethod
    def tier_discount(subtotal: Decimal,
                      tier: Optional[DiscountTier]) -> Decimal:
        if tier is None:
            return ZERO
        return money(subtotal * Decimal(tier.percent) / Decimal(100))

    @staticmethod
    def validate_promo_code(promo: PromoCode, subtotal: Decimal) -> None:
        """Raise :class:`PromoCodeError` describing why the code is unusable."""
        if promo.valid_to and promo.valid_to < timezone.now():
            raise PromoCodeError("This promo code has expired.")
        if promo.usage_limit and promo.used_count >= promo.usage_limit:
            raise PromoCodeError("This promo code has reached its usage limit.")
        if subtotal < promo.min_order:
            raise PromoCodeError(
                f"This promo code requires a minimum order of "
                f"{money(promo.min_order)}.")

    @classmethod
    def promo_discount(cls, promo: Optional[PromoCode],
                       base: Decimal) -> Decimal:
        if promo is None:
            return ZERO
        if promo.type == PromoCode.Type.PERCENT:
            return money(base * promo.value / Decimal(100))
        return money(min(promo.value, base))

    @classmethod
    def breakdown(cls, *, subtotal, promo_code: Optional[PromoCode] = None,
                  delivery_cost=ZERO) -> PriceBreakdown:
        """
        Compute every line of the price. An invalid promo code is ignored
        rather than raising — callers that need the reason validate first.
        """
        subtotal = money(subtotal)
        delivery_cost = money(delivery_cost)

        tier = cls.active_tier(subtotal)
        tier_discount = cls.tier_discount(subtotal, tier)

        applied_promo = promo_code
        if applied_promo is not None:
            try:
                cls.validate_promo_code(applied_promo, subtotal)
            except PromoCodeError:
                applied_promo = None

        after_tier = subtotal - tier_discount
        promo_discount = cls.promo_discount(applied_promo, after_tier)

        total = money(subtotal - tier_discount - promo_discount + delivery_cost)
        return PriceBreakdown(
            subtotal=subtotal,
            tier_discount=tier_discount,
            promo_discount=promo_discount,
            delivery_cost=delivery_cost,
            total=max(total, ZERO),
            tier=tier,
            promo_code=applied_promo,
        )
