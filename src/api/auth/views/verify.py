from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.users import services

from ..serializers.verify import (DetailSerializer,
                                  ResendVerificationSerializer,
                                  VerifyEmailSerializer)

User = get_user_model()

# Returned whether or not the address exists, so neither endpoint can be used
# to discover which emails are registered.
GENERIC_INVALID = {"code": ["Invalid or expired code."]}


@extend_schema(
    tags=["auth"],
    summary="Verify an email address",
    description=(
        "Consumes a verification code and activates the account. Codes are "
        "single-use, expire after `OTP_CODE_TTL_MINUTES`, and lock the flow "
        "for an hour after `OTP_MAX_ATTEMPTS` wrong guesses."
    ),
    request=VerifyEmailSerializer,
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class VerifyEmailView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyEmailSerializer
    throttle_scope = "otp"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.filter(email__iexact=data["email"]).first()
        if user is None:
            return Response(GENERIC_INVALID,
                            status=status.HTTP_400_BAD_REQUEST)

        services.verify_code(user, data["code"], services.PURPOSE_VERIFY)
        services.mark_verified(user)
        return Response({"detail": "Email verified. You can now log in."},
                        status=status.HTTP_200_OK)


@extend_schema(
    tags=["auth"],
    summary="Resend the verification code",
    description=(
        "Invalidates the previous code and emails a new one. Subject to a "
        "cooldown (`OTP_RESEND_COOLDOWN_SECONDS`) and a resend limit.\n\n"
        "Always responds `200` so the endpoint cannot be used to enumerate "
        "accounts."
    ),
    request=ResendVerificationSerializer,
    responses={200: DetailSerializer},
)
class ResendVerificationView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResendVerificationSerializer
    throttle_scope = "otp"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"]).first()
        if user is not None and not user.is_active:
            services.resend_code(user, services.PURPOSE_VERIFY)

        return Response(
            {"detail": "If the account exists and is unverified, "
                       "a new code has been sent."},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["auth"],
    summary="Verify an email address from a link",
    description=(
        "Alternative to the 6-digit code: the registration email may contain "
        "a one-time link ending in this UUID. Retained from the original "
        "implementation for clients that use `BASE_URL_LINK`."
    ),
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class VerifyEmailLinkView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = DetailSerializer
    throttle_scope = "otp"

    def get(self, request, link_id):
        from django.utils import timezone

        from apps.users.models import UserOTPIDVerifications

        link = UserOTPIDVerifications.objects.filter(code=link_id).first()
        if link is None or link.expired_at < timezone.now():
            return Response({"detail": "Invalid or expired link."},
                            status=status.HTTP_400_BAD_REQUEST)

        services.mark_verified(link.user)
        link.expired_at = timezone.now()
        link.save(update_fields=["expired_at"])
        return Response({"detail": "Email verified. You can now log in."},
                        status=status.HTTP_200_OK)
