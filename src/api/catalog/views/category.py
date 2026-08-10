from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.catalog.models import Category
from apps.catalog.selectors import category_queryset

from ..serializers.category import CategorySerializer, CategoryTreeSerializer


@extend_schema(tags=["catalog"], summary="List categories")
class CategoryListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    filter_backends = [drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["sort", "name", "product_count"]
    ordering = ["sort", "name"]

    def get_queryset(self):
        qs = category_queryset()
        if self.request.query_params.get("root") == "true":
            qs = qs.filter(parent__isnull=True)
        return qs


@extend_schema(
    tags=["catalog"],
    summary="Category tree",
    description="Root categories with their immediate children, for menus.",
)
class CategoryTreeView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategoryTreeSerializer
    pagination_class = None

    def get_queryset(self):
        return (category_queryset()
                .filter(parent__isnull=True)
                .prefetch_related(Prefetch(
                    "children",
                    queryset=Category.objects.filter(is_active=True)
                    .order_by("sort", "name"),
                    to_attr="prefetched_children"))
                .order_by("sort", "name"))


@extend_schema(tags=["catalog"], summary="Retrieve a category by slug")
class CategoryDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return category_queryset()
