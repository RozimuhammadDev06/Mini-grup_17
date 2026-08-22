from rest_framework import serializers


class QrGenerateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(required=False, allow_blank=True)


class QrResponseSerializer(serializers.Serializer):
    qr_image = serializers.CharField(
        help_text="Base64 PNG data URI — use directly as an <img> src.")
    payment_url = serializers.CharField()
    amount = serializers.CharField()
    merchant_trans_id = serializers.CharField()


class InvoiceCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    phone_number = serializers.CharField(max_length=20)


class InvoiceResponseSerializer(serializers.Serializer):
    error_code = serializers.IntegerField(required=False)
    error_note = serializers.CharField(required=False)
    invoice_id = serializers.IntegerField(required=False)
