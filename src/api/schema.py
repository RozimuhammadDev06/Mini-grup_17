"""
Audience-scoped OpenAPI schemas.

The full schema is dominated by the staff API, which a storefront developer
never calls. These preprocessing hooks split the same routes into two
documents so each audience reads only what it can use:

* ``/api/docs/``       — everything
* ``/api/docs/frontend/`` — auth, catalog, cart, user, content
* ``/api/docs/admin/``    — the staff API only

Nothing is duplicated: both documents are generated from the same views, so
they cannot drift apart.
"""

from __future__ import annotations

ADMIN_PREFIX = "/api/v1/admin/"

# Operational endpoints that sit outside /api/v1 and belong in both
# documents — both audiences need to know how to probe the service.
SHARED_PATHS = ("/healthz/",)


def frontend_endpoints(endpoints, **kwargs):
    """Drop the staff API from the storefront document."""
    return [
        endpoint for endpoint in endpoints
        if not endpoint[0].startswith(ADMIN_PREFIX)
    ]


def admin_endpoints(endpoints, **kwargs):
    """Keep only the staff API."""
    return [
        endpoint for endpoint in endpoints
        if endpoint[0].startswith(ADMIN_PREFIX)
        or endpoint[0] in SHARED_PATHS
    ]


FRONTEND_SETTINGS = {
    "TITLE": "Stroyopttorg Storefront API",
    "DESCRIPTION": (
        "Everything a storefront or mobile client needs: authentication, "
        "catalogue, cart, checkout and content.\n\n"
        "## Authentication\n"
        "`POST /api/v1/auth/login/` returns an `access` / `refresh` pair. "
        "Send the access token as `Authorization: Bearer <access>`; use "
        "**Authorize** above to try requests from this page.\n\n"
        "Access tokens last 60 minutes by default. When one expires, call "
        "`POST /api/v1/auth/token/refresh/`. `POST /api/v1/auth/logout/` "
        "blacklists the refresh token — the access token stays valid until "
        "it expires, so discard it client-side too.\n\n"
        "## Guests\n"
        "Cart and product comparison work without a token; the visitor is "
        "identified by the session cookie, so send credentials/cookies with "
        "those calls. Logging in merges the guest cart into the account.\n\n"
        "## Errors\n"
        "Non-field errors are `{\"detail\": \"...\"}`. Field validation "
        "errors are `{\"field\": [\"message\", ...]}`.\n\n"
        "## Paging\n"
        "List endpoints return `{count, pages, next, previous, results}` and "
        "accept `?page=` and `?page_size=` (max 100)."
    ),
    "VERSION": "1.0.0",
    "PREPROCESSING_HOOKS": ["api.schema.frontend_endpoints"],
    "TAGS": [
        {"name": "auth", "description":
            "Registration, email verification, login, logout, password "
            "reset."},
        {"name": "catalog", "description":
            "Categories, brands, products, filters, reviews, comparison."},
        {"name": "cart", "description":
            "Cart for guests and signed-in users, plus promo codes."},
        {"name": "user", "description":
            "The signed-in user's profile, addresses, orders, wishlist and "
            "reviews. Always scoped to the token."},
        {"name": "content", "description":
            "Home page, news, promotions, banners, FAQ, static pages, "
            "lead forms."},
        {"name": "ops", "description": "Health check."},
    ],
}

ADMIN_SETTINGS = {
    "TITLE": "Stroyopttorg Admin API",
    "DESCRIPTION": (
        "Staff-only management API. Every endpoint requires a JWT belonging "
        "to a user with `is_staff=True`; anyone else receives `403`."
    ),
    "VERSION": "1.0.0",
    "PREPROCESSING_HOOKS": ["api.schema.admin_endpoints"],
    "TAGS": [{"name": "admin", "description": "Staff management endpoints."}],
}
