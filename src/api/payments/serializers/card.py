"""
Card tokenization payloads.

`card_number` and `expire_date` are write-only and are forwarded straight to
the gateway — nothing here persists them, and the gateway's masked
`card_number` is what comes back to the client.
"""

import re

from rest_framework import serializers


class CardTokenRequestSerializer(serializers.Serializer):
    card_number = serializers.CharField(
        write_only=True, min_length=12, max_length=19,
        help_text="PAN, digits only. Never stored by this backend.")
    expire_date = serializers.CharField(
        write_only=True, min_length=4, max_length=4,
        help_text="MMYY, e.g. 1228.")
    temporary = serializers.BooleanField(
        default=False,
        help_text="true issues a one-shot token instead of a reusable one.")

    def validate_card_number(self, value: str) -> str:
        digits = re.sub(r"[\s-]", "", value)
        if not digits.isdigit():
            raise serializers.ValidationError(
                "Card number must contain digits only.")
        return digits

    def validate_expire_date(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(
                "Expiry must be four digits in MMYY format.")
        month = int(value[:2])
        if not 1 <= month <= 12:
            raise serializers.ValidationError("Expiry month must be 01-12.")
        return value


class CardTokenVerifySerializer(serializers.Serializer):
    card_token = serializers.CharField(max_length=255)
    sms_code = serializers.CharField(min_length=4, max_length=8)


class CardTokenPaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    card_token = serializers.CharField(max_length=255)


class GatewayPassthroughSerializer(serializers.Serializer):
    """The gateway's own response body, forwarded unchanged."""

    error_code = serializers.IntegerField(required=False)
    error_note = serializers.CharField(required=False)
