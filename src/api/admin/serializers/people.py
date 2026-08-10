from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.leads.models import Lead
from apps.reviews.models import Review

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name",
                  "phone_number", "language", "is_active", "is_staff",
                  "date_joined", "last_login")
        read_only_fields = ("id", "email", "full_name", "date_joined",
                            "last_login")


class AdminReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "user", "product", "author_name", "rating", "comment",
                  "is_published", "created_at", "updated_at")
        read_only_fields = ("id", "user", "product", "created_at",
                            "updated_at")


class AdminLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ("id", "type", "name", "phone", "product", "consent",
                  "status", "created_at")
        read_only_fields = ("id", "type", "name", "phone", "product",
                            "consent", "created_at")
