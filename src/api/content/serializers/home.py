from rest_framework import serializers

from api.catalog.serializers.category import CategorySerializer
from api.catalog.serializers.product import ProductListSerializer

from .article import ArticleListSerializer
from .banner import BannerSerializer
from .promotion import PromotionSerializer


class HomeSerializer(serializers.Serializer):
    """Documents the shape of the aggregated home payload."""

    banners = BannerSerializer(many=True)
    categories = CategorySerializer(many=True)
    popular_products = ProductListSerializer(many=True)
    best_selling_products = ProductListSerializer(many=True)
    new_products = ProductListSerializer(many=True)
    discounted_products = ProductListSerializer(many=True)
    featured_products = ProductListSerializer(many=True)
    promotions = PromotionSerializer(many=True)
    news = ArticleListSerializer(many=True)
