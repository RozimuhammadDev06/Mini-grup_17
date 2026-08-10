from rest_framework import serializers

from apps.reviews.models import Review


class ProductReviewSerializer(serializers.ModelSerializer):
    """Public read view of a review. Never exposes the reviewer's email."""

    class Meta:
        model = Review
        fields = ("id", "product", "author_name", "rating", "comment",
                  "created_at", "updated_at")
        read_only_fields = fields


class RatingSummarySerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    average_rating = serializers.FloatField()
    review_count = serializers.IntegerField()
    distribution = serializers.DictField(child=serializers.IntegerField())
