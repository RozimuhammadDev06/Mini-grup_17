from rest_framework import serializers

from apps.content.models import Banner


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ("id", "title", "image", "link", "sort")
        read_only_fields = fields
