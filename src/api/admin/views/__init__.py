from .catalog import (AdminBrandViewSet, AdminCategoryViewSet,
                      AdminProductImageViewSet, AdminProductViewSet,
                      AdminStockViewSet)
from .content import (AdminArticleViewSet, AdminBannerViewSet,
                      AdminDiscountTierViewSet, AdminFaqViewSet,
                      AdminPromoCodeViewSet, AdminPromotionViewSet,
                      AdminStaticPageViewSet)
from .order import AdminOrderViewSet
from .people import AdminLeadViewSet, AdminReviewViewSet, AdminUserViewSet

__all__ = [
    "AdminArticleViewSet", "AdminBannerViewSet", "AdminBrandViewSet",
    "AdminCategoryViewSet", "AdminDiscountTierViewSet", "AdminFaqViewSet",
    "AdminLeadViewSet", "AdminOrderViewSet", "AdminProductImageViewSet",
    "AdminProductViewSet", "AdminPromoCodeViewSet", "AdminPromotionViewSet",
    "AdminReviewViewSet", "AdminStaticPageViewSet", "AdminStockViewSet",
    "AdminUserViewSet",
]
