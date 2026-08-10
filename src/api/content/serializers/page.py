from rest_framework import serializers

from apps.content.models import StaticPage


class StaticPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticPage
        fields = ("id", "slug", "title", "body")
        read_only_fields = fields
