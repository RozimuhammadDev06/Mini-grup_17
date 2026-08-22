"""
Signed passthrough to the Fintechhub Merchant API.

The gateway requires an ``Auth: <user_id>:<sha1(timestamp+secret)>:<timestamp>``
header on every ``/api/v2/merchant/`` request. These endpoints compute it
server-side so a client never needs the merchant secret — the mistake being
avoided is the Postman pre-request script that hardcodes the secret.

**Staff only.** The signature is our merchant identity: anyone who can call
this endpoint can spend and refund money as us. The operation allowlist in
``apps.payments.operations`` bounds what is reachable.
"""

import time

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsStaff
from apps.payments.gateway import (ConfigurationError, GatewayError,
                                   build_auth_header, get_client)
from apps.payments.operations import OPERATIONS

from ..serializers.gateway import (AuthHeaderSerializer,
                                   GatewayCallResponseSerializer,
                                   GatewayCallSerializer)

# The gateway accepts timestamps within 300 seconds of its own clock.
AUTH_HEADER_TTL_SECONDS = 300


@extend_schema(
    tags=["payments"],
    summary="Call a Fintechhub endpoint through a signed proxy",
    description=(
        "Sends a request to the gateway with the `Auth` header calculated "
        "server-side, and returns the gateway's response verbatim.\n\n"
        "Only allowlisted operations are reachable — an arbitrary path proxy "
        "would let a caller refund payments using our merchant signature. "
        "`GET` this endpoint for the operation catalogue.\n\n"
        "**Staff only.**"
    ),
    request=GatewayCallSerializer,
    responses={200: GatewayCallResponseSerializer},
    examples=[
        OpenApiExample(
            "Check a payment status",
            value={"operation": "payment_status",
                   "payload": {"payment_id": 34}},
            request_only=True),
        OpenApiExample(
            "Create a hosted payment session",
            value={"operation": "pay_init",
                   "payload": {"merchant_trans_id": "ORDER-1001",
                               "amount": "125000.00"}},
            request_only=True),
    ],
)
class GatewayProxyView(GenericAPIView):
    permission_classes = [IsStaff]
    serializer_class = GatewayCallSerializer

    def get(self, request):
        """Catalogue of callable operations and their arguments."""
        return Response({
            "base_url": settings.FINTECHHUB_BASE_URL,
            "service_id": settings.FINTECHHUB_SERVICE_ID,
            "operations": [
                {
                    "operation": name,
                    "required": list(op.required),
                    "optional": list(op.optional),
                    "requires_card_data": op.card_data,
                    "enabled": (not op.card_data
                                or settings
                                .FINTECHHUB_ENABLE_CARD_TOKENIZATION),
                    "description": op.description,
                }
                for name, op in sorted(OPERATIONS.items())
            ],
        })

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["operation"]
        payload = dict(serializer.validated_data.get("payload") or {})
        operation = OPERATIONS[name]

        if operation.card_data and not \
                settings.FINTECHHUB_ENABLE_CARD_TOKENIZATION:
            return Response(
                {"detail": f"'{name}' needs card tokenization, which is "
                           f"disabled (FINTECHHUB_ENABLE_CARD_TOKENIZATION)."},
                status=status.HTTP_403_FORBIDDEN)

        unknown = sorted(set(payload) - set(operation.allowed))
        if unknown:
            return Response(
                {"payload": [f"Unsupported argument(s): {', '.join(unknown)}. "
                             f"Allowed: {', '.join(operation.allowed)}."]},
                status=status.HTTP_400_BAD_REQUEST)

        absent = [key for key in operation.required if key not in payload]
        if absent:
            return Response(
                {"payload": [f"Missing required argument(s): "
                             f"{', '.join(absent)}."]},
                status=status.HTTP_400_BAD_REQUEST)

        client = get_client()
        call = getattr(client, operation.method)
        started = time.monotonic()
        try:
            body = (call(payload[operation.required[0]]) if operation.positional
                    else call(**payload))
        except ConfigurationError as exc:
            return Response(
                {"operation": name, "ok": False, "http_status": None,
                 "elapsed_ms": int((time.monotonic() - started) * 1000),
                 "response": {}, "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except GatewayError as exc:
            return Response(
                {"operation": name, "ok": False,
                 "http_status": exc.status_code,
                 "elapsed_ms": int((time.monotonic() - started) * 1000),
                 "response": exc.payload if isinstance(exc.payload, dict)
                 else {}, "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "operation": name,
            "ok": True,
            "http_status": 200,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "response": body,
        })


@extend_schema(
    tags=["payments"],
    summary="Generate a Merchant API Auth header",
    description=(
        "Returns a freshly signed `Auth` header for manual testing in Postman "
        "or curl, so the merchant secret never has to be pasted into a client "
        "script. Valid for 300 seconds.\n\n**Staff only.**"
    ),
    responses={200: AuthHeaderSerializer},
)
class GatewayAuthHeaderView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        if not settings.FINTECHHUB_MERCHANT_USER_ID or \
                not settings.FINTECHHUB_MERCHANT_SECRET_KEY:
            return Response(
                {"detail": "Merchant credentials are not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        timestamp = int(time.time())
        return Response({
            "auth_header": build_auth_header(timestamp=timestamp),
            "merchant_user_id": settings.FINTECHHUB_MERCHANT_USER_ID,
            "timestamp": timestamp,
            "expires_in_seconds": AUTH_HEADER_TTL_SECONDS,
            "base_url": settings.FINTECHHUB_BASE_URL,
            "service_id": settings.FINTECHHUB_SERVICE_ID,
        })
