from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters, status
from rest_framework.decorators import action
from rest_framework.mixins import (CreateModelMixin, ListModelMixin,
                                   RetrieveModelMixin)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.carts import services as cart_services
from apps.carts.sessions import guest_session_key
from apps.orders import services as order_services
from apps.orders.models import Order

from ..filters.order import OrderFilter
from ..serializers.order import (OrderCreateSerializer, OrderDetailSerializer,
                                 OrderListSerializer)


@extend_schema(tags=["orders"])
class OrderViewSet(CreateModelMixin, ListModelMixin, RetrieveModelMixin,
                   GenericViewSet):
    """
    Orders placed from the caller's session — no account needed.

    ``get_queryset`` is always scoped to the caller (see
    ``order_services.owned_orders``), so an id belonging to another visitor
    is a 404 — there is no code path that can read someone else's order.
    """

    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    queryset = Order.objects.none()
    filterset_class = OrderFilter
    ordering_fields = ["created_at", "total", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return order_services.owned_orders(self.request)

    def get_throttles(self):
        # Placing an order reserves stock and a guest has no account to
        # rate-limit, so checkout gets its own per-client budget.
        self.throttle_scope = "checkout" if self.action == "create" else None
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action == "retrieve":
            return OrderDetailSerializer
        return OrderListSerializer

    @extend_schema(
        summary="Place an order from the caller's cart",
        description=(
            "Guest checkout: no account is needed. The order belongs to the "
            "session cookie that owns the cart, so send cookies with this "
            "call and with every later call for the order or its payment.\n\n"
            "Runs in a single transaction: stock rows are locked with "
            "`SELECT FOR UPDATE`, quantities re-validated, prices re-read "
            "from the catalogue, snapshots written, stock decremented and "
            "the cart emptied. Any failure rolls the whole thing back.\n\n"
            "Delivery needs `city_id` from `GET /api/v1/geo/cities/`, which "
            "prices the delivery and names the city on the address.\n\n"
            "A card order left unpaid until `payment_due_at` is cancelled "
            "and its stock released.\n\n"
            "Money is never taken from the request body."
        ),
        request=OrderCreateSerializer,
        responses={201: OrderDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = cart_services.resolve_cart(request, create=False)
        if cart is None:
            return Response({"detail": ["Your cart is empty."]},
                            status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        address = data.get("address")
        order = order_services.create_order_from_cart(
            user=user,
            session_key=None if user else guest_session_key(request),
            cart=cart,
            address_snapshot=(
                {**address, "phone": data["customer_phone"]}
                if address else {}),
            customer={
                "name": data["customer_name"],
                "phone": data["customer_phone"],
                "email": data["customer_email"],
            },
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
