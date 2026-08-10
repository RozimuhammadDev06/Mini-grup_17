from rest_framework import serializers

from apps.orders.models import Order, OrderItem


class AdminOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "product", "name_snapshot", "article_snapshot",
                  "price", "quantity")
        read_only_fields = fields


class AdminOrderSerializer(serializers.ModelSerializer):
    items = AdminOrderItemSerializer(many=True, read_only=True)
    customer_email = serializers.EmailField(
        source="user.email", read_only=True, default=None)

    class Meta:
        model = Order
        fields = ("id", "number", "user", "customer_email", "status",
                  "delivery_type", "payment_method", "address_snapshot",
                  "subtotal", "cart_discount", "promo_discount",
                  "delivery_cost", "total", "items", "created_at", "paid_at")
        # Money and contents are derived at checkout; staff may only move the
        # order through its status machine.
        read_only_fields = tuple(f for f in fields if f != "status")


class AdminOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
