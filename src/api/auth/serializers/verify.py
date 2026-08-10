from rest_framework import serializers


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class DetailSerializer(serializers.Serializer):
    """Generic ``{"detail": "..."}`` response body."""

    detail = serializers.CharField()
