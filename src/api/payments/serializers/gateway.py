from rest_framework import serializers

from apps.payments.operations import OPERATIONS


class GatewayCallSerializer(serializers.Serializer):
    operation = serializers.ChoiceField(
        choices=sorted(OPERATIONS),
        help_text="Allowlisted gateway operation to invoke.")
    payload = serializers.DictField(
        required=False, default=dict,
        help_text="Arguments for the operation. Unknown keys are rejected.")


class GatewayCallResponseSerializer(serializers.Serializer):
    operation = serializers.CharField()
    ok = serializers.BooleanField()
    http_status = serializers.IntegerField(allow_null=True)
    elapsed_ms = serializers.IntegerField()
    response = serializers.DictField()
    detail = serializers.CharField(required=False)


class AuthHeaderSerializer(serializers.Serializer):
    auth_header = serializers.CharField()
    merchant_user_id = serializers.CharField()
    timestamp = serializers.IntegerField()
    expires_in_seconds = serializers.IntegerField()
    base_url = serializers.CharField()
    service_id = serializers.IntegerField()
