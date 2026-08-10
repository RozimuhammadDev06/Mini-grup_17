"""
Published-content querysets and the home-page aggregate.

The home payload is assembled with a fixed number of queries (one per
section) and cached in Redis; nothing here iterates a queryset to issue
further queries.
"""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from .models import Article, Banner, Faq, Promotion, StaticPage

HOME_CACHE_KEY = "home:v1"
SECTION_SIZE = 10


def published_articles() -> QuerySet[Article]:
    return Article.objects.filter(
        published_at__isnull=False, published_at__lte=timezone.now())


def active_promotions() -> QuerySet[Promotion]:
    """Undated promotions never expire; dated ones drop out after the date."""
    today = timezone.now().date()
    return Promotion.objects.filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    ).select_related("category")


def banners() -> QuerySet[Banner]:
    return Banner.objects.all().order_by("sort")


def faqs() -> QuerySet[Faq]:
    return Faq.objects.all().order_by("sort")


def static_page(slug: str) -> StaticPage | None:
    return StaticPage.objects.filter(slug=slug).first()


def home_sections(request=None) -> dict:
    """Build every home-page section. Callers should prefer ``cached_home``."""
    from apps.catalog.selectors import category_queryset, product_queryset

    products = product_queryset()

    return {
        "banners": list(banners()[:SECTION_SIZE]),
        "categories": list(
            category_queryset().filter(parent__isnull=True)[:SECTION_SIZE]),
        "popular_products": list(
            products.order_by("-review_count", "-rating")[:SECTION_SIZE]),
        "best_selling_products": list(
            products.order_by("-sold_count", "-created_at")[:SECTION_SIZE]),
        "new_products": list(products.order_by("-created_at")[:SECTION_SIZE]),
        "discounted_products": list(
            products.filter(old_price__isnull=False, old_price__gt=F("price"))
            .order_by("-created_at")[:SECTION_SIZE]),
        "featured_products": list(
            products.filter(is_featured=True)
            .order_by("-created_at")[:SECTION_SIZE]),
        "promotions": list(active_promotions()[:SECTION_SIZE]),
        "news": list(
            published_articles().order_by("-published_at")[:SECTION_SIZE]),
    }


def invalidate_home_cache() -> None:
    cache.delete(HOME_CACHE_KEY)
