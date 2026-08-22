from rest_framework import serializers

from apps.payments.models import Payment


class PaymentInitSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default="")
    return_url = serializers.URLField(required=False, allow_blank=True)


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "order", "order_number", "provider", "provider_id",
                  "payment_type", "status", "amount", "created_at")
        read_only_fields = fields


class PaymentInitResponseSerializer(serializers.Serializer):
    payment = PaymentSerializer()
    payment_id = serializers.CharField(
        help_text="Gateway payment id, used by the checkout UI.")
    return_url = serializers.CharField()
    amount = serializers.CharField()
