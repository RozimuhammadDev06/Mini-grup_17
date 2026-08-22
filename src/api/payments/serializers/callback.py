from rest_framework import serializers


class PrepareCallbackSerializer(serializers.Serializer):
    """Shop API prepare payload (form-encoded)."""

    click_trans_id = serializers.CharField()
    service_id = serializers.CharField()
    click_paydoc_id = serializers.CharField(required=False, allow_blank=True)
    merchant_trans_id = serializers.CharField()
    amount = serializers.CharField()
    action = serializers.IntegerField()
    error = serializers.IntegerField(required=False, default=0)
    error_note = serializers.CharField(required=False, allow_blank=True,
                                       default="")
    sign_time = serializers.CharField()
    sign_string = serializers.CharField()


class CompleteCallbackSerializer(PrepareCallbackSerializer):
    merchant_prepare_id = serializers.CharField()


class CallbackResponseSerializer(serializers.Serializer):
    error = serializers.IntegerField()
    error_note = serializers.CharField()
    merchant_prepare_id = serializers.IntegerField(required=False)
    merchant_confirm_id = serializers.IntegerField(required=False)
