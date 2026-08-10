from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.users.validators import validate_password_strength


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyResetCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(
        write_only=True, trim_whitespace=False)
    new_password2 = serializers.CharField(
        write_only=True, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password_strength(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": ["Passwords do not match."]})
        return attrs
