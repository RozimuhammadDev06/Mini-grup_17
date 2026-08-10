from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.content.models import Promotion
from apps.content.selectors import active_promotions

from ..serializers.promotion import (PromotionDetailSerializer,
                                     PromotionSerializer)


@extend_schema(
    tags=["content"],
    summary="List active promotions",
    description=("Expired promotions (`valid_until` in the past) are excluded "
                 "— they can never appear as active."),
)
class PromotionListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PromotionSerializer
    filter_backends = [drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ["title", "body", "discount_label"]
    ordering_fields = ["valid_until", "title"]

    def get_queryset(self):
        return active_promotions()


@extend_schema(tags=["content"], summary="Retrieve a promotion by slug")
class PromotionDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PromotionDetailSerializer
    lookup_field = "slug"
    queryset = Promotion.objects.select_related("category")
