from rest_framework import serializers

from apps.content.models import Article


class ArticleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ("id", "type", "title", "slug", "image", "published_at")
        read_only_fields = fields


class ArticleDetailSerializer(ArticleListSerializer):
    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ("body",)
        read_only_fields = fields
