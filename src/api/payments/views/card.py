"""
Card tokenization endpoints (Merchant API passthrough).

**PCI-DSS note.** These endpoints accept a raw PAN, which places this service
in scope for PCI-DSS. The card number is forwarded to the gateway inside the
request that carries it and is never written to the database, the logs, or the
error payloads. The alternative — `/payments/init/`, where the customer enters
the card on the gateway's own page — keeps this backend out of scope.

Flow: request (issues an SMS challenge) -> verify (activates the token) ->
pay (charges it; the gateway then calls our prepare/complete callbacks).
"""

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import Http404
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments.gateway import GatewayError, get_client
from apps.payments.models import Payment

from ..serializers.card import (CardTokenPaymentSerializer,
                                CardTokenRequestSerializer,
                                CardTokenVerifySerializer,
                                GatewayPassthroughSerializer)

logger = logging.getLogger(__name__)


class CardTokenizationMixin:
    """
    Gate for the PCI-scoped endpoints.

    Disabled by default: a deployment that never enables this cannot be made
    to accept a PAN, whatever a client sends.
    """

    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        if not settings.FINTECHHUB_ENABLE_CARD_TOKENIZATION:
            raise Http404("Card tokenization is disabled.")
        super().initial(request, *args, **kwargs)


def gateway_error_response(exc: GatewayError) -> Response:
    """Surface the gateway's reason without leaking the request body."""
    return Response({"detail": str(exc)},
                    status=status.HTTP_502_BAD_GATEWAY
                    if exc.status_code is None
                    else status.HTTP_400_BAD_REQUEST)


def _own_order(request, order_id):
    return Order.objects.filter(pk=order_id, user=request.user).first()


@extend_schema(
    tags=["payments"],
    summary="Tokenize a card",
    description=(
        "Exchanges a card number for a token and triggers the gateway's SMS "
        "challenge. The PAN is forwarded to the gateway and is never stored "
        "or logged here; the response carries only a masked number.\n\n"
        "**This endpoint puts your deployment in PCI-DSS scope.** Prefer "
        "`/payments/init/` unless you must collect cards yourself."
    ),
    request=CardTokenRequestSerializer,
    responses={200: GatewayPassthroughSerializer},
)
class CardTokenRequestView(CardTokenizationMixin, GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CardTokenRequestSerializer
    throttle_scope = "otp"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = get_client().card_token_request(
                card_number=data["card_number"],
                expire_date=data["expire_date"],
                temporary=data["temporary"],
            )
        except GatewayError as exc:
            logger.info("Card tokenization refused for user %s", request.user.pk)
            return gateway_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["payments"],
    summary="Verify a card token with the SMS code",
    request=CardTokenVerifySerializer,
    responses={200: GatewayPassthroughSerializer},
)
class CardTokenVerifyView(CardTokenizationMixin, GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CardTokenVerifySerializer
    throttle_scope = "otp"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = get_client().card_token_verify(
                card_token=data["card_token"], sms_code=data["sms_code"])
        except GatewayError as exc:
            return gateway_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["payments"],
    summary="Charge a verified card token",
    description=(
        "Charges the token for the order total. The gateway responds by "
        "calling this backend's `prepare_url` and `complete_url`, so the "
        "order is marked paid through the Shop API — not from this response "
        "alone. Poll the order, or call `/payments/{id}/sync/`, to observe "
        "the final state."
    ),
    request=CardTokenPaymentSerializer,
    responses={200: GatewayPassthroughSerializer},
)
class CardTokenPaymentView(CardTokenizationMixin, GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CardTokenPaymentSerializer
    throttle_scope = "login"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order = _own_order(request, data["order_id"])
        if order is None:
            return Response({"detail": "Order not found."},
                            status=status.HTTP_404_NOT_FOUND)
        if order.paid_at is not None:
            return Response({"detail": "This order is already paid."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = get_client().card_token_payment(
                card_token=data["card_token"],
                amount=order.total,
                merchant_trans_id=order.number,
            )
        except GatewayError as exc:
            return gateway_error_response(exc)

        # The callbacks may already have created the row; record the id either
        # way so reconciliation can find it.
        payment_id = str(payload.get("payment_id", ""))
        if payment_id:
            Payment.objects.update_or_create(
                provider=Payment.Provider.FINTECHHUB,
                provider_id=payment_id,
                defaults={"order": order, "amount": order.total,
                          "payment_type": Payment.PaymentType.CARD},
            )
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["payments"],
    summary="Delete a card token",
    responses={200: GatewayPassthroughSerializer},
)
class CardTokenDeleteView(CardTokenizationMixin, APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, card_token):
        try:
            payload = get_client().card_token_delete(card_token)
        except GatewayError as exc:
            return gateway_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
