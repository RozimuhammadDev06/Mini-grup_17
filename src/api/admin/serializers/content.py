from rest_framework import serializers

from apps.content.models import Article, Banner, Faq, Promotion, StaticPage
from apps.discounts.models import DiscountTier, PromoCode


class AdminArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ("id", "type", "title", "slug", "body", "image",
                  "published_at")


class AdminPromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = ("id", "title", "slug", "body", "image", "discount_label",
                  "valid_until", "category")


class AdminBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ("id", "title", "image", "link", "sort")


class AdminFaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ("id", "question", "answer", "sort")


class AdminStaticPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticPage
        fields = ("id", "slug", "title", "body")


class AdminPromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = ("id", "code", "type", "value", "min_order", "valid_to",
                  "usage_limit", "used_count")
        read_only_fields = ("id", "used_count")


class AdminDiscountTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountTier
        fields = ("id", "threshold", "percent", "is_active")
