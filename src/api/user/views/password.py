from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users import services
from apps.users.models import ChangePasswordLogs

from ..serializers.password import ChangePasswordSerializer


@extend_schema(
    tags=["user"],
    summary="Change the caller's password",
    description=(
        "Requires the current password. On success **every refresh token for "
        "the account is revoked**, so other sessions cannot mint new access "
        "tokens; the caller must log in again.\n\n"
        "An audit row is written to `ChangePasswordLogs` recording that a "
        "change happened — it deliberately stores no password material."
    ),
    request=ChangePasswordSerializer,
)
class ChangePasswordView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        now = timezone.now()
        ChangePasswordLogs.objects.create(
            user=user, expired_at=now, error_expired_at=now, is_changed=True)

        revoked = services.revoke_all_refresh_tokens(user)
        return Response(
            {"detail": "Password changed. Please log in again.",
             "revoked_sessions": revoked},
            status=status.HTTP_200_OK)
