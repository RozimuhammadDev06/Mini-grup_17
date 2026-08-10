from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.users import services

from ..serializers.register import (RegisterResponseSerializer,
                                    RegisterSerializer)


@extend_schema(
    tags=["auth"],
    summary="Register a new account",
    description=(
        "Creates an **unverified** account and emails a 6-digit verification "
        "code. The account cannot log in until `/auth/verify/` succeeds.\n\n"
        "Registering with an address that already exists returns `400`; it "
        "never modifies the existing account."
    ),
    request=RegisterSerializer,
    responses={201: RegisterResponseSerializer},
)
class RegisterView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_scope = "register"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = services.register_user(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data.get("last_name", ""),
            phone_number=data.get("phone_number", ""),
        )
        return Response(
            {"detail": "Verification code sent to your email.",
             "email": user.email},
            status=status.HTTP_201_CREATED,
        )
