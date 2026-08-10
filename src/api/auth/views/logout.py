from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users import services

from ..serializers.login import LogoutSerializer
from ..serializers.verify import DetailSerializer


@extend_schema(
    tags=["auth"],
    summary="Log out (revoke refresh tokens)",
    description=(
        "**How logout actually works here.** JWT access tokens are "
        "self-contained and cannot be revoked; this endpoint blacklists the "
        "*refresh* token so no new access token can be minted from it. The "
        "access token the client already holds stays valid until it expires "
        "(`JWT_ACCESS_TOKEN_LIFETIME`, 60 minutes by default) — clients must "
        "discard it.\n\n"
        "Pass `all_devices: true` to blacklist every outstanding refresh "
        "token for the account."
    ),
    request=LogoutSerializer,
    responses={200: DetailSerializer},
)
class LogoutView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("all_devices"):
            count = services.revoke_all_refresh_tokens(request.user)
            return Response(
                {"detail": f"Logged out. {count} refresh token(s) revoked."},
                status=status.HTTP_200_OK)

        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response({"refresh": ["Invalid or already revoked token."]},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
