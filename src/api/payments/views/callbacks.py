"""
Shop API callback endpoints (Fintechhub-payment → this backend).

These are server-to-server, so they are unauthenticated in the DRF sense and
CSRF-exempt; trust comes entirely from the MD5 signature computed with the
service secret. A request that fails signature validation is answered with
`error: -1` and changes nothing.

Both handlers always return HTTP 200 with an error code in the body — that is
the protocol. A non-200 would make the gateway retry a request we have already
definitively rejected.
"""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.payments import services

from ..serializers.callback import (CallbackResponseSerializer,
                                    CompleteCallbackSerializer,
                                    PrepareCallbackSerializer)


class BaseCallbackView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def _run(self, request, handler):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            # Malformed payloads are a protocol error, not a DRF 400.
            return Response(
                services.error_response(services.ERR_ACTION_NOT_FOUND),
                status=status.HTTP_200_OK)
        return Response(handler(serializer.validated_data),
                        status=status.HTTP_200_OK)


@extend_schema(
    tags=["payments"],
    summary="Shop API: prepare callback",
    description=(
        "Called by Fintechhub-payment before confirming a payment. Validates "
        "the MD5 signature, checks the order exists and the amount matches, "
        "reserves the order and returns a stable `merchant_prepare_id`.\n\n"
        "Idempotent: a replayed prepare returns the same id.\n\n"
        "Configure this URL as the service's `prepare_url`."
    ),
    request=PrepareCallbackSerializer,
    responses={200: CallbackResponseSerializer},
)
class PrepareCallbackView(BaseCallbackView):
    serializer_class = PrepareCallbackSerializer

    def post(self, request):
        return self._run(request, services.handle_prepare)


@extend_schema(
    tags=["payments"],
    summary="Shop API: complete callback",
    description=(
        "Called after prepare succeeds. Marks the order paid and returns a "
        "stable `merchant_confirm_id`.\n\n"
        "A negative `error` field means the gateway is reversing the payment: "
        "the order is marked refunded and its stock returned.\n\n"
        "Configure this URL as the service's `complete_url`."
    ),
    request=CompleteCallbackSerializer,
    responses={200: CallbackResponseSerializer},
)
class CompleteCallbackView(BaseCallbackView):
    serializer_class = CompleteCallbackSerializer

    def post(self, request):
        return self._run(request, services.handle_complete)
