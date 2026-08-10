from rest_framework import serializers

from apps.content.models import Faq


class FaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ("id", "question", "answer", "sort")
        read_only_fields = fields
