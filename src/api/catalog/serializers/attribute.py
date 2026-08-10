from rest_framework import serializers

from apps.catalog.models import Attribute, AttributeValue, ProductAttribute


class AttributeValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttributeValue
        fields = ("id", "value_string", "value_number")


class AttributeSerializer(serializers.ModelSerializer):
    values = AttributeValueSerializer(many=True, read_only=True)

    class Meta:
        model = Attribute
        fields = ("id", "code", "name", "unit", "type", "is_filterable",
                  "is_comparable", "values")


class ProductAttributeSerializer(serializers.ModelSerializer):
    """One characteristic of a product, flattened for direct rendering."""

    code = serializers.CharField(source="attribute.code", read_only=True)
    name = serializers.CharField(source="attribute.name", read_only=True)
    unit = serializers.CharField(source="attribute.unit", read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttribute
        fields = ("attribute_id", "code", "name", "unit", "value")

    def get_value(self, obj) -> str | None:
        if obj.value_number is not None:
            return str(obj.value_number)
        if obj.value is not None:
            return obj.value.value_string or str(obj.value.value_number)
        return None
