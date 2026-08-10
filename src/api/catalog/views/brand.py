from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.catalog.models import Brand

from ..serializers.brand import BrandSerializer


@extend_schema(tags=["catalog"], summary="List brands")
class BrandListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()
    filter_backends = [drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name"]
    ordering = ["name"]


@extend_schema(tags=["catalog"], summary="Retrieve a brand by slug")
class BrandDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()
    lookup_field = "slug"
