"""Shared object builders for the API test suite."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalog.models import (Attribute, AttributeValue, Brand, Category,
                                 Product, ProductAttribute, Stock)
from apps.discounts.models import DiscountTier, PromoCode

User = get_user_model()

PASSWORD = "StrongPass1!"


def create_user(email="user@example.com", *, verified=True, staff=False,
                **extra) -> User:
    user = User(
        email=email,
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", "User"),
        is_active=verified,
        is_staff=staff,
        is_superuser=extra.pop("is_superuser", False),
        **extra,
    )
    user.set_password(PASSWORD)
    user.save()
    return user


def create_category(name="Tools", slug="tools", **extra) -> Category:
    # get_or_create so factories that fall back to the default category can
    # be called repeatedly within one test.
    category, _ = Category.objects.get_or_create(
        slug=slug, defaults={"name": name, **extra})
    return category


def create_brand(name="Bosch", slug="bosch") -> Brand:
    brand, _ = Brand.objects.get_or_create(
        slug=slug, defaults={"name": name})
    return brand


def create_product(*, category=None, brand=None, name="Drill", slug="drill",
                   article="ART-1", price="100.00", old_price=None,
                   stock=10, is_active=True, is_featured=False) -> Product:
    product = Product.objects.create(
        category=category or create_category(),
        brand=brand,
        name=name,
        slug=slug,
        article=article,
        price=Decimal(price),
        old_price=Decimal(old_price) if old_price else None,
        is_active=is_active,
        is_featured=is_featured,
    )
    Stock.objects.create(
        product=product, quantity=stock,
        status=Stock.Status.IN_STOCK if stock else Stock.Status.OUT_OF_STOCK,
        synced_at=timezone.now())
    return product


def create_attribute(code="power", name="Power", unit="W",
                     value="1500") -> tuple[Attribute, AttributeValue]:
    attribute = Attribute.objects.create(code=code, name=name, unit=unit)
    attribute_value = AttributeValue.objects.create(
        attribute=attribute, value_string=value)
    return attribute, attribute_value


def attach_attribute(product, attribute, attribute_value) -> ProductAttribute:
    return ProductAttribute.objects.create(
        product=product, attribute=attribute, value=attribute_value)


def create_promo_code(code="SAVE10", percent=10, min_order="0",
                      usage_limit=None) -> PromoCode:
    return PromoCode.objects.create(
        code=code, type=PromoCode.Type.PERCENT, value=Decimal(percent),
        min_order=Decimal(min_order), usage_limit=usage_limit)


def create_discount_tier(threshold="1000", percent=5) -> DiscountTier:
    return DiscountTier.objects.create(
        threshold=Decimal(threshold), percent=percent, is_active=True)


def auth_client(client, user):
    """Attach a real JWT for ``user`` to an APIClient."""
    from apps.users.services import issue_tokens
    tokens = issue_tokens(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client
