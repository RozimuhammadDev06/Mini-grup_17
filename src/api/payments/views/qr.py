"""QR payment and invoice endpoints."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments.gateway import GatewayError, get_client

from ..serializers.qr import (InvoiceCreateSerializer,
                              InvoiceResponseSerializer, QrGenerateSerializer,
                              QrResponseSerializer)
from .card import gateway_error_response


def _own_order(request, order_id):
    return Order.objects.filter(pk=order_id, user=request.user).first()


@extend_schema(
    tags=["payments"],
    summary="Generate a payment QR code for an order",
    description=(
        "Returns a base64 PNG data URI and the click.uz URL encoded inside "
        "it. The customer scans it, pays in the click.uz app, and the gateway "
        "calls this backend's `complete_url`."
    ),
    request=QrGenerateSerializer,
    responses={200: QrResponseSerializer},
)
class QrGenerateView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QrGenerateSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order = _own_order(request, data["order_id"])
        if order is None:
            return Response({"detail": "Order not found."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            payload = get_client().qr_generate(
                amount=order.total,
                merchant_trans_id=order.number,
                return_url=data.get("return_url") or None,
            )
        except GatewayError as exc:
            return gateway_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["payments"],
    summary="Create an invoice for an order",
    description=("Sends a payable invoice to the customer's phone number. "
                 "Poll the invoice status endpoint for the outcome."),
    request=InvoiceCreateSerializer,
    responses={201: InvoiceResponseSerializer},
)
class InvoiceCreateView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceCreateSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order = _own_order(request, data["order_id"])
        if order is None:
            return Response({"detail": "Order not found."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            payload = get_client().create_invoice(
                merchant_trans_id=order.number,
                amount=order.total,
                phone_number=data["phone_number"],
            )
        except GatewayError as exc:
            return gateway_error_response(exc)
        return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["payments"],
    summary="Check invoice status",
    description="Statuses: `created`, `paid`, `expired`, `cancelled`.",
    responses={200: InvoiceResponseSerializer},
)
class InvoiceStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        try:
            payload = get_client().invoice_status(invoice_id)
        except GatewayError as exc:
            return gateway_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
