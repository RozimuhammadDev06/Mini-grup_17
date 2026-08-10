from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.models import Review
from apps.reviews.selectors import product_rating_summary

from ..serializers.review import (ProductReviewSerializer,
                                  RatingSummarySerializer)


@extend_schema(
    tags=["catalog"],
    summary="List reviews for a product",
    description=("Only published reviews. Supports `?rating=5`, "
                 "`?ordering=-created_at|created_at|rating|-rating`."),
)
class ProductReviewListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductReviewSerializer
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_fields = ["rating"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]
    queryset = Review.objects.none()

    def get_queryset(self):
        return Review.objects.filter(
            product_id=self.kwargs["product_id"], is_published=True)


@extend_schema(
    tags=["catalog"],
    summary="Rating summary for a product",
    description="Server-computed average and per-star distribution.",
    responses=RatingSummarySerializer,
)
class ProductRatingSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        return Response(product_rating_summary(product_id))
