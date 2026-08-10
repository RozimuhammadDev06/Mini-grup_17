from django.urls import path

from .views import (CartAddItemView, CartDetailView, CartItemView,
                    CartPromoView)

app_name = "cart"

urlpatterns = [
    path("", CartDetailView.as_view(), name="detail"),
    path("items/", CartAddItemView.as_view(), name="add-item"),
    path("items/<int:product_id>/", CartItemView.as_view(), name="item"),
    path("promo/", CartPromoView.as_view(), name="promo"),
]
