from rest_framework import serializers

from apps.carts.models import Cart, CartItem
from apps.carts.services import price_breakdown, subtotal

from api.catalog.serializers.product import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "product", "quantity", "price", "total")
        read_only_fields = ("id", "price", "total")


class CartSerializer(serializers.ModelSerializer):
    """The cart plus a fully server-computed price breakdown."""

    items = CartItemSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()
    promo_code = serializers.CharField(
        source="promo_code.code", read_only=True, default=None)

    class Meta:
        model = Cart
        fields = ("id", "items", "promo_code", "totals", "updated_at")

    def get_totals(self, obj) -> dict:
        breakdown = price_breakdown(obj)
        return {
            "subtotal": str(breakdown.subtotal),
            "cart_discount": str(breakdown.tier_discount),
            "promo_discount": str(breakdown.promo_discount),
            "discount_total": str(breakdown.discount_total),
            "delivery_cost": str(breakdown.delivery_cost),
            "total": str(breakdown.total),
            "tier_percent": breakdown.tier.percent if breakdown.tier else 0,
            "item_count": sum(i.quantity for i in obj.items.all()),
        }


class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(
        min_value=0, help_text="0 removes the line from the cart.")


class PromoCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
