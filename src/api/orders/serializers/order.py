from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.orders import services as order_services
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
    payment_due_at = serializers.SerializerMethodField(
        help_text="For an unpaid card order: when it is cancelled and its "
                  "stock released if still unpaid. Null otherwise.")

    class Meta:
        model = Order
        fields = ("id", "number", "status", "status_display", "delivery_type",
                  "payment_method", "total", "item_count", "created_at",
                  "paid_at", "payment_due_at")
        read_only_fields = fields

    def get_item_count(self, obj) -> int:
        return sum(item.quantity for item in obj.items.all())

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_payment_due_at(self, obj):
        due = order_services.payment_due_at(obj)
        return serializers.DateTimeField().to_representation(due) if due else None


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + (
            "items", "customer_name", "customer_phone", "customer_email",
            "address_snapshot", "subtotal", "cart_discount",
            "promo_discount", "delivery_cost")
        read_only_fields = fields


class CheckoutAddressSerializer(serializers.Serializer):
    """
    Delivery address typed in at checkout — guests have no saved ones.

    City and region are not typed: they come from ``city_id``, the city the
    delivery is priced for.
    """

    company_name = serializers.CharField(
        max_length=255, allow_blank=True, default="")
    street = serializers.CharField(max_length=255)
    house = serializers.CharField(max_length=50, allow_blank=True, default="")


class OrderCreateSerializer(serializers.Serializer):
    """
    Checkout input. Contents and money come from the server-side cart —
    the client only says who to contact, where to deliver and how to pay.
    """

    customer_name = serializers.CharField(max_length=150)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(allow_blank=True, default="")
    address = CheckoutAddressSerializer(
        required=False,
        help_text="Required unless delivery_type is 'pickup'.")
    delivery_type = serializers.ChoiceField(
        choices=Order.DeliveryType.choices,
        default=Order.DeliveryType.DELIVERY)
    payment_method = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices, default=Order.PaymentMethod.CARD)
    city_id = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Required unless delivery_type is 'pickup'. One of the "
                  "cities from GET /api/v1/geo/cities/; it sets the "
                  "delivery price.")

    def validate_customer_name(self, value: str) -> str:
        if len(value) < 2:
            raise serializers.ValidationError(
                "Name must be at least 2 characters.")
        return value

    def validate_customer_phone(self, value: str) -> str:
        if len([c for c in value if c.isdigit()]) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs.get("delivery_type") != Order.DeliveryType.PICKUP:
            errors = {}
            if not attrs.get("address"):
                errors["address"] = ["An address is required for delivery."]
            if not attrs.get("city_id"):
                errors["city_id"] = ["A city is required for delivery."]
            if errors:
                raise serializers.ValidationError(errors)
        return attrs
