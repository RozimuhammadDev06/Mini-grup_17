from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class AuthUserSerializer(serializers.ModelSerializer):
    """The public shape of the authenticated user. Never includes password."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name",
                  "phone_number", "language", "is_active")
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    user = AuthUserSerializer()
    tokens = TokenPairSerializer()


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        help_text="The refresh token to revoke.")
    all_devices = serializers.BooleanField(
        default=False,
        help_text="Revoke every refresh token issued to this account.")
