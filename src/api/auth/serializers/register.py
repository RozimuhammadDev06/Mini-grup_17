from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.users.validators import validate_password_strength

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=50)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, min_length=2)
    last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default="")
    phone_number = serializers.CharField(
        max_length=13, required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        normalized = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=normalized).exists():
            # Registration is rate limited, so this does not give an attacker
            # a practical enumeration oracle, and the alternative (silently
            # accepting) is far worse UX.
            raise serializers.ValidationError(
                "An account with this email already exists.")
        return normalized

    def validate_password(self, value: str) -> str:
        try:
            validate_password_strength(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": ["Passwords do not match."]})
        return attrs


class RegisterResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    email = serializers.EmailField()
