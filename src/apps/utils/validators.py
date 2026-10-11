"""
Field validators shared by the catalogue and content models.

They are attached to model fields, so the Django admin (model forms) and the
staff API (ModelSerializers copy model-field validators) enforce exactly the
same rules from a single definition.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

# Swagger UI pre-fills every string field with "string". Records created by
# pressing "Execute" without editing the example are the usual source of junk
# catalogue rows, so that literal is rejected wherever a real name is needed.
PLACEHOLDER_VALUES = frozenset({"string"})

# Lowercase ASCII words joined by single hyphens or underscores: "power-tools".
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
MIN_SLUG_LENGTH = 2


def validate_not_placeholder(value: str) -> None:
    """Reject whitespace-only values and API-example placeholders."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError("This field cannot be blank.", code="blank")
    if cleaned.lower() in PLACEHOLDER_VALUES:
        raise ValidationError(
            "'%(value)s' is an API example placeholder, not a real value.",
            code="placeholder", params={"value": cleaned})


def validate_lowercase_slug(value: str) -> None:
    """Slugs end up in public URLs, so they must be canonical lowercase."""
    if len(value or "") < MIN_SLUG_LENGTH or not SLUG_PATTERN.match(value):
        raise ValidationError(
            "Use at least %(min)d lowercase letters or digits, separated by "
            "single hyphens or underscores (for example 'power-tools').",
            code="invalid_slug", params={"min": MIN_SLUG_LENGTH})


def validate_safe_link(value: str) -> None:
    """
    Links rendered as ``href`` by the storefront.

    Only site-relative paths ("/catalog/") and absolute http(s) URLs are
    allowed: a ``javascript:`` or ``data:`` link would execute in every
    visitor's browser.
    """
    link = (value or "").strip()
    if not link:
        return
    if link != value or any(ch.isspace() for ch in link):
        raise ValidationError("Links cannot contain whitespace.",
                              code="invalid_link")
    if link.startswith("/") and not link.startswith(("//", "/\\")):
        return
    parts = urlsplit(link)
    if parts.scheme in ("http", "https") and parts.netloc:
        return
    raise ValidationError(
        "Enter a site path starting with '/' or a full http(s) URL.",
        code="invalid_link")
