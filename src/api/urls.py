"""
API v1 root.

One include per audience module — auth flows, the signed-in user's own
resources, the public catalogue, the cart (guest or signed-in), public
content, payments, and the staff-only admin API.
"""

from django.urls import include, path

urlpatterns = [
    # Disabled: the site runs without login and registration.
    # path("auth/", include("api.auth.urls")),
    # Disabled: the site runs without login and registration, so there are
    # no accounts — orders moved to the guest-checkout module below.
    # path("user/", include("api.user.urls")),
    path("orders/", include("api.orders.urls")),
    path("geo/", include("api.geo.urls")),
    path("admin/", include("api.admin.urls")),
    path("catalog/", include("api.catalog.urls")),
    path("cart/", include("api.cart.urls")),
    path("payments/", include("api.payments.urls")),
    path("", include("api.content.urls")),
]
