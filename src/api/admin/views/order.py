from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.mixins import (ListModelMixin, RetrieveModelMixin,
                                   UpdateModelMixin)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.orders.models import Order

from ..serializers.order import (AdminOrderSerializer,
                                 AdminOrderStatusSerializer)
from .base import StaffModelViewSet


@extend_schema(tags=["admin"])
class AdminOrderViewSet(ListModelMixin, RetrieveModelMixin, UpdateModelMixin,
                        GenericViewSet):
    """
    Staff view of all orders. Orders are never created or deleted here —
    they originate from customer checkout, and deleting one would destroy the
    financial record.
    """

    permission_classes = StaffModelViewSet.permission_classes
    filter_backends = StaffModelViewSet.filter_backends
    queryset = (Order.objects
                .select_related("user")
                .prefetch_related("items"))
    serializer_class = AdminOrderSerializer
    search_fields = ["number", "user__email"]
    ordering_fields = ["created_at", "total", "status"]
    filterset_fields = ["status", "delivery_type", "payment_method"]

    @extend_schema(
        summary="Move an order to a new status",
        request=AdminOrderStatusSerializer,
        responses=AdminOrderSerializer,
    )
    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        order = self.get_object()
        serializer = AdminOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.status = serializer.validated_data["status"]
        order.save(update_fields=["status"])
        return Response(AdminOrderSerializer(order).data)
