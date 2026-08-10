from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product, ProductImage

from .attribute import ProductAttributeSerializer
from .brand import BrandSerializer
from .category import CategorySerializer


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "sort", "is_main")


class StockSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)


class ProductListSerializer(serializers.ModelSerializer):
    """Card representation. Aggregates come from the selector's annotations."""

    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    main_image = serializers.SerializerMethodField()
    discount_percent = serializers.IntegerField(read_only=True)
    rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True, default=Decimal("0"))
    review_count = serializers.IntegerField(read_only=True, default=0)
    stock_quantity = serializers.IntegerField(read_only=True, default=0)
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "name", "slug", "article", "price", "old_price",
                  "discount_percent", "brand", "category", "main_image",
                  "rating", "review_count", "stock_quantity", "in_stock",
                  "is_featured", "created_at")

    def get_main_image(self, obj) -> str | None:
        images = list(obj.images.all())
        if not images:
            return None
        main = next((i for i in images if i.is_main), images[0])
        request = self.context.get("request")
        url = main.image.url
        return request.build_absolute_uri(url) if request else url

    def get_in_stock(self, obj) -> bool:
        return bool(getattr(obj, "stock_quantity", 0) > 0)


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(
        source="product_attributes", many=True, read_only=True)
    stock = StockSerializer(read_only=True)
    is_in_wishlist = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            "description", "attrs_json", "images", "attributes", "stock",
            "is_in_wishlist")

    def get_is_in_wishlist(self, obj) -> bool:
        from apps.carts.compare_services import is_in_wishlist
        request = self.context.get("request")
        if request is None:
            return False
        return is_in_wishlist(request.user, obj.pk)
