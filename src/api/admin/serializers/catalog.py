from rest_framework import serializers

from apps.catalog.models import (Brand, Category, Product, ProductImage,
                                 Stock)


class AdminCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "parent", "name", "slug", "sort", "is_active")


class AdminBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug", "logo")


class AdminProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "product", "image", "sort", "is_main")


class AdminProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "category", "brand", "name", "slug", "article",
                  "price", "old_price", "description", "attrs_json",
                  "is_active", "is_featured", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value


class AdminStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name", read_only=True)

    class Meta:
        model = Stock
        fields = ("id", "product", "product_name", "quantity", "status",
                  "synced_at")

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value
