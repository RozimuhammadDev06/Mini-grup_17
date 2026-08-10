from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework.mixins import (ListModelMixin, RetrieveModelMixin,
                                   UpdateModelMixin)
from rest_framework.viewsets import GenericViewSet

from apps.leads.models import Lead
from apps.reviews.models import Review

from ..serializers.people import (AdminLeadSerializer, AdminReviewSerializer,
                                  AdminUserSerializer)
from .base import StaffModelViewSet

User = get_user_model()


@extend_schema(tags=["admin"])
class AdminUserViewSet(ListModelMixin, RetrieveModelMixin, UpdateModelMixin,
                       GenericViewSet):
    """Read and lightly edit accounts. Deletion is left to Django admin."""

    permission_classes = StaffModelViewSet.permission_classes
    filter_backends = StaffModelViewSet.filter_backends
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    search_fields = ["email", "first_name", "last_name", "phone_number"]
    ordering_fields = ["date_joined", "email"]
    filterset_fields = ["is_active", "is_staff"]


@extend_schema(tags=["admin"], summary="Moderate reviews")
class AdminReviewViewSet(StaffModelViewSet):
    queryset = Review.objects.select_related("user", "product")
    serializer_class = AdminReviewSerializer
    search_fields = ["author_name", "comment", "product__name"]
    ordering_fields = ["created_at", "rating"]
    filterset_fields = ["is_published", "rating", "product"]


@extend_schema(tags=["admin"], summary="Work the lead queue")
class AdminLeadViewSet(StaffModelViewSet):
    queryset = Lead.objects.select_related("product")
    serializer_class = AdminLeadSerializer
    search_fields = ["name", "phone"]
    ordering_fields = ["created_at"]
    filterset_fields = ["status", "type"]
