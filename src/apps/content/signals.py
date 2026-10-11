"""
Keep the cached home payload in step with the rows it is built from.

The staff API already invalidates the cache in its views; these receivers
cover every other write path — the Django admin, shell sessions, management
commands — so a product created, moved between categories, unpublished or
deleted anywhere shows up on the home page (and in its category counts)
straight away rather than after the cache TTL.
"""

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .selectors import invalidate_home_cache

HOME_SOURCE_MODELS = (
    "catalog.Category",
    "catalog.Brand",
    "catalog.Product",
    "catalog.ProductImage",
    "catalog.Stock",
    "content.Article",
    "content.Promotion",
    "content.Banner",
)


def _invalidate_home(sender, **kwargs):
    if kwargs.get("raw"):  # loaddata: the cache is rebuilt on first request
        return
    # After commit, so a concurrent request cannot re-cache pre-commit rows.
    transaction.on_commit(invalidate_home_cache, robust=True)


def connect_signals():
    for label in HOME_SOURCE_MODELS:
        model = apps.get_model(label)
        post_save.connect(_invalidate_home, sender=model,
                          dispatch_uid=f"home-cache:save:{label}")
        post_delete.connect(_invalidate_home, sender=model,
                            dispatch_uid=f"home-cache:delete:{label}")
