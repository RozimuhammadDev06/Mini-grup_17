from rest_framework import serializers

from apps.catalog.models import Category


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "sort", "product_count")


class CategoryTreeSerializer(CategorySerializer):
    """Two-level tree; deeper nesting is not used by the storefront."""

    children = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ("children",)

    def get_children(self, obj) -> list:
        children = getattr(obj, "prefetched_children", None)
        if children is None:
            children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True).data
