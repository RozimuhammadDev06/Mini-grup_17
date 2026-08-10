from rest_framework import serializers

from apps.carts.models import Wishlist

from api.catalog.serializers.product import ProductListSerializer


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = Wishlist
        fields = ("id", "product")


class WishlistAddSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)


class WishlistStatusSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    in_wishlist = serializers.BooleanField()
