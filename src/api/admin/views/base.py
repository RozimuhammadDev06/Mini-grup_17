from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters
from rest_framework.viewsets import ModelViewSet

from api.permissions import IsStaff


class StaffModelViewSet(ModelViewSet):
    """Base for every admin endpoint: staff-only, searchable, orderable."""

    permission_classes = [IsStaff]
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter,
                       drf_filters.OrderingFilter]
