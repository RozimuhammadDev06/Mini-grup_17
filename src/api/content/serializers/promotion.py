from rest_framework import serializers

from apps.content.models import Promotion


class PromotionSerializer(serializers.ModelSerializer):
    category_slug = serializers.SlugField(
        source="category.slug", read_only=True, default=None)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = ("id", "title", "slug", "image", "discount_label",
                  "valid_until", "category", "category_slug", "is_active")
        read_only_fields = fields

    def get_is_active(self, obj) -> bool:
        from django.utils import timezone
        return obj.valid_until is None or obj.valid_until >= timezone.now().date()


class PromotionDetailSerializer(PromotionSerializer):
    class Meta(PromotionSerializer.Meta):
        fields = PromotionSerializer.Meta.fields + ("body",)
        read_only_fields = fields
