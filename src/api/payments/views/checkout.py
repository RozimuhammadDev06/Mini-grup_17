"""Customer-facing payment endpoints (checkout → this backend → gateway)."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments import services
from apps.payments.gateway import GatewayError
from apps.payments.models import Payment

from ..serializers.checkout import (PaymentInitResponseSerializer,
                                    PaymentInitSerializer, PaymentSerializer)


@extend_schema(
    tags=["payments"],
    summary="Start a payment for an order",
    description=(
        "Opens a Fintechhub payment session for one of the caller's own "
        "orders and returns the gateway `payment_id` the checkout UI needs.\n\n"
        "Calling it twice for the same order reuses the existing session "
        "rather than creating a second charge. The order moves to "
        "`awaiting_payment`."
    ),
    request=PaymentInitSerializer,
    responses={201: PaymentInitResponseSerializer},
)
class PaymentInitView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentInitSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Scoped to request.user: another account's order id is a 404.
        order = Order.objects.filter(
            pk=data["order_id"], user=request.user).first()
        if order is None:
            return Response({"detail": "Order not found."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            payment = services.start_payment(
                order,
                phone_number=data.get("phone_number", ""),
                return_url=data.get("return_url") or None,
            )
        except GatewayError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "payment": PaymentSerializer(payment).data,
            "payment_id": payment.provider_id,
            "return_url": payment.raw_response.get("return_url", ""),
            "amount": str(payment.amount),
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["payments"],
    summary="List the caller's payments for an order",
    responses=PaymentSerializer(many=True),
)
class OrderPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = Order.objects.filter(pk=order_id, user=request.user).first()
        if order is None:
            return Response({"detail": "Order not found."},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(
            PaymentSerializer(order.payments.all(), many=True).data)


@extend_schema(
    tags=["payments"],
    summary="Re-check a payment's status with the gateway",
    description=("Reconciliation for a missed callback: asks the gateway for "
                 "the authoritative status and updates the order if it has "
                 "moved on."),
    request=None,
    responses={200: PaymentSerializer},
)
class PaymentSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        payment = Payment.objects.filter(
            pk=payment_id, order__user=request.user).first()
        if payment is None:
            return Response({"detail": "Payment not found."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            payment = services.sync_payment_status(payment)
        except GatewayError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response(PaymentSerializer(payment).data)
