from rest_framework import serializers

from apps.carts.compare_services import (MAX_COMPARE_PRODUCTS,
                                         MIN_COMPARE_PRODUCTS)


class ComparisonRequestSerializer(serializers.Serializer):
    product_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=MIN_COMPARE_PRODUCTS,
        max_length=MAX_COMPARE_PRODUCTS,
    )


class CompareItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()


class ComparisonAttributeRowSerializer(serializers.Serializer):
    attribute_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    unit = serializers.CharField()
    is_common = serializers.BooleanField()
    values = serializers.DictField(child=serializers.CharField(
        allow_null=True))
