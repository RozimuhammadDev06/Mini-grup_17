from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (AddressViewSet, ChangePasswordView, MyReviewViewSet,
                    OrderViewSet, ProfileView, WishlistAddView,
                    WishlistItemView, WishlistListView, WishlistStatusView)

app_name = "user"

router = DefaultRouter()
router.include_root_view = False
router.register("addresses", AddressViewSet, basename="address")
router.register("orders", OrderViewSet, basename="order")
router.register("reviews", MyReviewViewSet, basename="review")

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password/change/", ChangePasswordView.as_view(),
         name="password-change"),

    path("wishlist/", WishlistListView.as_view(), name="wishlist"),
    path("wishlist/add/", WishlistAddView.as_view(), name="wishlist-add"),
    path("wishlist/<int:product_id>/", WishlistItemView.as_view(),
         name="wishlist-item"),
    path("wishlist/<int:product_id>/status/", WishlistStatusView.as_view(),
         name="wishlist-status"),

    path("", include(router.urls)),
]
