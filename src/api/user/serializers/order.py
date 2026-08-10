from rest_framework import serializers

from apps.orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Reads the snapshot columns, never the live product row."""

    total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    product_slug = serializers.SlugField(
        source="product.slug", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_slug", "name_snapshot",
                  "article_snapshot", "price", "quantity", "total")
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ("id", "number", "status", "status_display", "delivery_type",
                  "payment_method", "total", "item_count", "created_at",
                  "paid_at")
        read_only_fields = fields

    def get_item_count(self, obj) -> int:
        return sum(item.quantity for item in obj.items.all())


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + (
            "items", "address_snapshot", "subtotal", "cart_discount",
            "promo_discount", "delivery_cost")
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    """
    Checkout input. Contents and money come from the server-side cart —
    the client only chooses an address and how to receive and pay.
    """

    address_id = serializers.IntegerField(
        required=False,
        help_text="One of the caller's saved addresses. Required unless "
                  "delivery_type is 'pickup'.")
    delivery_type = serializers.ChoiceField(
        choices=Order.DeliveryType.choices,
        default=Order.DeliveryType.DELIVERY)
    payment_method = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices, default=Order.PaymentMethod.CARD)
    city_id = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Used to price delivery from the city's delivery zone.")

    def validate(self, attrs: dict) -> dict:
        if (attrs.get("delivery_type") != Order.DeliveryType.PICKUP
                and not attrs.get("address_id")):
            raise serializers.ValidationError(
                {"address_id": ["An address is required for delivery."]})
        return attrs
