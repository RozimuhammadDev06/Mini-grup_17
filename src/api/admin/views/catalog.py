from drf_spectacular.utils import extend_schema

from apps.catalog.models import (Brand, Category, Product, ProductImage,
                                 Stock)
from apps.content.selectors import invalidate_home_cache

from ..serializers.catalog import (AdminBrandSerializer,
                                   AdminCategorySerializer,
                                   AdminProductImageSerializer,
                                   AdminProductSerializer,
                                   AdminStockSerializer)
from .base import StaffModelViewSet


class CacheInvalidatingMixin:
    """Catalogue edits must not linger behind the cached home page."""

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_home_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_home_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_home_cache()


@extend_schema(tags=["admin"])
class AdminCategoryViewSet(CacheInvalidatingMixin, StaffModelViewSet):
    queryset = Category.objects.select_related("parent")
    serializer_class = AdminCategorySerializer
    search_fields = ["name", "slug"]
    ordering_fields = ["sort", "name"]
    filterset_fields = ["is_active", "parent"]


@extend_schema(tags=["admin"])
class AdminBrandViewSet(CacheInvalidatingMixin, StaffModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = AdminBrandSerializer
    search_fields = ["name", "slug"]
    ordering_fields = ["name"]


@extend_schema(tags=["admin"])
class AdminProductViewSet(CacheInvalidatingMixin, StaffModelViewSet):
    queryset = Product.objects.select_related("category", "brand", "stock")
    serializer_class = AdminProductSerializer
    search_fields = ["name", "article", "slug"]
    ordering_fields = ["created_at", "price", "name"]
    filterset_fields = ["is_active", "is_featured", "category", "brand"]


@extend_schema(tags=["admin"])
class AdminProductImageViewSet(StaffModelViewSet):
    queryset = ProductImage.objects.select_related("product")
    serializer_class = AdminProductImageSerializer
    filterset_fields = ["product", "is_main"]
    ordering_fields = ["sort"]


@extend_schema(tags=["admin"], summary="Manage stock levels")
class AdminStockViewSet(StaffModelViewSet):
    queryset = Stock.objects.select_related("product")
    serializer_class = AdminStockSerializer
    search_fields = ["product__name", "product__article"]
    ordering_fields = ["quantity", "synced_at"]
    filterset_fields = ["status"]
