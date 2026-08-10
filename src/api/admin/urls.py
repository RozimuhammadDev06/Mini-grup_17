from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (AdminArticleViewSet, AdminBannerViewSet,
                    AdminBrandViewSet, AdminCategoryViewSet,
                    AdminDiscountTierViewSet, AdminFaqViewSet,
                    AdminLeadViewSet, AdminOrderViewSet,
                    AdminProductImageViewSet, AdminProductViewSet,
                    AdminPromoCodeViewSet, AdminPromotionViewSet,
                    AdminReviewViewSet, AdminStaticPageViewSet,
                    AdminStockViewSet, AdminUserViewSet)

app_name = "admin_api"

router = DefaultRouter()
router.include_root_view = False
router.register("categories", AdminCategoryViewSet, basename="category")
router.register("brands", AdminBrandViewSet, basename="brand")
router.register("products", AdminProductViewSet, basename="product")
router.register("product-images", AdminProductImageViewSet,
                basename="product-image")
router.register("stock", AdminStockViewSet, basename="stock")
router.register("orders", AdminOrderViewSet, basename="order")
router.register("users", AdminUserViewSet, basename="user")
router.register("reviews", AdminReviewViewSet, basename="review")
router.register("leads", AdminLeadViewSet, basename="lead")
router.register("articles", AdminArticleViewSet, basename="article")
router.register("promotions", AdminPromotionViewSet, basename="promotion")
router.register("banners", AdminBannerViewSet, basename="banner")
router.register("faq", AdminFaqViewSet, basename="faq")
router.register("pages", AdminStaticPageViewSet, basename="page")
router.register("promo-codes", AdminPromoCodeViewSet, basename="promo-code")
router.register("discount-tiers", AdminDiscountTierViewSet,
                basename="discount-tier")

urlpatterns = [path("", include(router.urls))]
