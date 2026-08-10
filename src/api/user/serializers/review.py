from rest_framework import serializers

from apps.reviews.models import Review


class MyReviewSerializer(serializers.ModelSerializer):
    """
    The user's own review. ``user`` and ``is_published`` are read-only so a
    reviewer cannot post as somebody else or self-publish.
    """

    class Meta:
        model = Review
        fields = ("id", "product", "author_name", "rating", "comment",
                  "is_published", "created_at", "updated_at")
        read_only_fields = ("id", "is_published", "created_at", "updated_at")

    def validate_rating(self, value: int) -> int:
        if not 1 <= value <= 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5.")
        return value

    def validate_comment(self, value: str) -> str:
        cleaned = (value or "").strip()
        if cleaned and len(cleaned) < 3:
            raise serializers.ValidationError(
                "Comment must be at least 3 characters.")
        return cleaned
