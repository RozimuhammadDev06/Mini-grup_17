from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.users import services

from ..serializers.password_reset import (ForgotPasswordSerializer,
                                          ResetPasswordSerializer,
                                          VerifyResetCodeSerializer)
from ..serializers.verify import DetailSerializer

NEUTRAL_RESPONSE = {
    "detail": "If an account exists for this email, a reset code has been "
              "sent."
}


@extend_schema(
    tags=["auth"],
    summary="Request a password reset code",
    description=(
        "Always responds `200` with the same body whether or not the address "
        "is registered, so the endpoint cannot be used to enumerate accounts."
    ),
    request=ForgotPasswordSerializer,
    responses={200: DetailSerializer},
)
class ForgotPasswordView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.begin_password_reset(serializer.validated_data["email"])
        return Response(NEUTRAL_RESPONSE, status=status.HTTP_200_OK)


@extend_schema(
    tags=["auth"],
    summary="Verify a password reset code",
    description=(
        "Confirms the code and opens a 30-minute window during which "
        "`/auth/reset-password/` will accept it. The code is *not* consumed "
        "here — it must be presented again to set the new password."
    ),
    request=VerifyResetCodeSerializer,
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class VerifyResetCodeView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyResetCodeSerializer
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.verify_reset_code(data["email"], data["code"])
        return Response(
            {"detail": "Code accepted. Set a new password within 30 minutes."},
            status=status.HTTP_200_OK)


@extend_schema(
    tags=["auth"],
    summary="Set a new password",
    description=(
        "Completes the reset. The code is consumed and cannot be replayed, "
        "and **every outstanding refresh token for the account is revoked** — "
        "a reset is assumed to mean the account may have been compromised."
    ),
    request=ResetPasswordSerializer,
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class ResetPasswordView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.reset_password(
            data["email"], data["code"], data["new_password"])
        return Response(
            {"detail": "Password updated. Please log in again."},
            status=status.HTTP_200_OK)
