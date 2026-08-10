from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters, status
from rest_framework.decorators import action
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.carts import services as cart_services
from apps.orders import services as order_services
from apps.orders.models import Order
from apps.users.models import Address

from ..filters.order import OrderFilter
from ..permissions import IsOwner
from ..serializers.order import (OrderCreateSerializer, OrderDetailSerializer,
                                 OrderListSerializer)


@extend_schema(tags=["user"])
class OrderViewSet(CreateModelMixin, ListModelMixin, RetrieveModelMixin,
                   GenericViewSet):
    """
    The caller's orders.

    ``get_queryset`` filters on ``request.user`` unconditionally, so an id
    belonging to someone else is a 404 — there is no code path that can read
    another account's order.
    """

    permission_classes = [IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    queryset = Order.objects.none()
    filterset_class = OrderFilter
    ordering_fields = ["created_at", "total", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return order_services.order_queryset(self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        return OrderListSerializer

    @extend_schema(
        summary="Place an order from the caller's cart",
        description=(
            "Runs in a single transaction: stock rows are locked with "
            "`SELECT FOR UPDATE`, quantities re-validated, prices re-read "
            "from the catalogue, snapshots written, stock decremented and "
            "the cart emptied. Any failure rolls the whole thing back.\n\n"
            "Money is never taken from the request body."
        ),
        request=OrderCreateSerializer,
        responses={201: OrderDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        address_snapshot = {}
        address_id = data.get("address_id")
        if address_id:
            address = Address.objects.filter(
                pk=address_id, user=request.user).first()
            if address is None:
                return Response(
                    {"address_id": ["Address not found."]},
                    status=status.HTTP_404_NOT_FOUND)
            address_snapshot = address.as_snapshot()

        cart = cart_services.resolve_cart(request, create=False)
        if cart is None:
            return Response({"detail": ["Your cart is empty."]},
                            status=status.HTTP_400_BAD_REQUEST)

        order = order_services.create_order_from_cart(
            user=request.user,
            cart=cart,
            address_snapshot=address_snapshot,
            delivery_type=data["delivery_type"],
            payment_method=data["payment_method"],
            city_id=data.get("city_id"),
        )
        return Response(
            OrderDetailSerializer(order, context={"request": request}).data,
            status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Cancel an order",
        description=("Allowed only while the order is new, awaiting payment "
                     "or processing. Reserved stock is returned."),
        request=None,
        responses={200: OrderDetailSerializer},
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = order_services.cancel_order(self.get_object())
        return Response(
            OrderDetailSerializer(order, context={"request": request}).data)
