from .address import AddressViewSet
from .order import OrderViewSet
from .password import ChangePasswordView
from .profile import ProfileView
from .review import MyReviewViewSet
from .wishlist import (WishlistAddView, WishlistItemView, WishlistListView,
                       WishlistStatusView)

__all__ = [
    "AddressViewSet",
    "ChangePasswordView",
    "MyReviewViewSet",
    "OrderViewSet",
    "ProfileView",
    "WishlistAddView",
    "WishlistItemView",
    "WishlistListView",
    "WishlistStatusView",
]
