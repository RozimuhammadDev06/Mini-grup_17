from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.carts import services as cart_services
from apps.users import services

from ..serializers.login import (AuthUserSerializer, LoginResponseSerializer,
                                 LoginSerializer)

User = get_user_model()

# One dummy hash comparison keeps the response time for "no such account"
# close to that of "wrong password", so timing does not leak which emails
# are registered.
_DUMMY_HASH = (
    "pbkdf2_sha256$600000$dummysaltdummysalt$"
    "PB0Xk5rGmm0dR0z3wKQBu2vN8gJ2m0J9pM2m0e3vJ1s="
)


@extend_schema(
    tags=["auth"],
    summary="Log in and obtain a JWT pair",
    description=(
        "Returns an access/refresh token pair.\n\n"
        "* `401` — wrong email or password.\n"
        "* `403` — the account exists but the email is not verified.\n\n"
        "Any cart built up as a guest in this session is merged into the "
        "account's cart on success."
    ),
    request=LoginSerializer,
    responses={200: LoginResponseSerializer},
)
class LoginView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = "login"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            check_password(password, _DUMMY_HASH)
            return Response({"detail": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"detail": "Invalid email or password."},
                            status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response(
                {"detail": "Email address is not verified.",
                 "code": "email_not_verified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        cart_services.merge_guest_cart(request, user)
        tokens = services.issue_tokens(user)
        return Response(
            {"user": AuthUserSerializer(user).data, "tokens": tokens},
            status=status.HTTP_200_OK,
        )
