from drf_spectacular.utils import extend_schema

from apps.content.models import Article, Banner, Faq, Promotion, StaticPage
from apps.content.selectors import invalidate_home_cache
from apps.discounts.models import DiscountTier, PromoCode

from ..serializers.content import (AdminArticleSerializer,
                                   AdminBannerSerializer,
                                   AdminDiscountTierSerializer,
                                   AdminFaqSerializer,
                                   AdminPromoCodeSerializer,
                                   AdminPromotionSerializer,
                                   AdminStaticPageSerializer)
from .base import StaffModelViewSet
from .catalog import CacheInvalidatingMixin


@extend_schema(tags=["admin"])
class AdminArticleViewSet(CacheInvalidatingMixin, StaffModelViewSet):
    queryset = Article.objects.all()
    serializer_class = AdminArticleSerializer
    search_fields = ["title", "body"]
    ordering_fields = ["published_at", "title"]
    filterset_fields = ["type"]


@extend_schema(tags=["admin"])
class AdminPromotionViewSet(CacheInvalidatingMixin, StaffModelViewSet):
    queryset = Promotion.objects.select_related("category")
    serializer_class = AdminPromotionSerializer
    search_fields = ["title", "body"]
    ordering_fields = ["valid_until", "title"]


@extend_schema(tags=["admin"])
class AdminBannerViewSet(CacheInvalidatingMixin, StaffModelViewSet):
    queryset = Banner.objects.all()
    serializer_class = AdminBannerSerializer
    ordering_fields = ["sort"]


@extend_schema(tags=["admin"])
class AdminFaqViewSet(StaffModelViewSet):
    queryset = Faq.objects.all()
    serializer_class = AdminFaqSerializer
    search_fields = ["question", "answer"]
    ordering_fields = ["sort"]


@extend_schema(tags=["admin"])
class AdminStaticPageViewSet(StaffModelViewSet):
    queryset = StaticPage.objects.all()
    serializer_class = AdminStaticPageSerializer
    search_fields = ["title", "slug", "body"]


@extend_schema(tags=["admin"])
class AdminPromoCodeViewSet(StaffModelViewSet):
    queryset = PromoCode.objects.all()
    serializer_class = AdminPromoCodeSerializer
    search_fields = ["code"]
    ordering_fields = ["code", "valid_to"]
    filterset_fields = ["type"]


@extend_schema(tags=["admin"])
class AdminDiscountTierViewSet(StaffModelViewSet):
    queryset = DiscountTier.objects.all()
    serializer_class = AdminDiscountTierSerializer
    ordering_fields = ["threshold", "percent"]
    filterset_fields = ["is_active"]
