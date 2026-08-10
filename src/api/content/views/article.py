from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.content.selectors import published_articles

from ..serializers.article import (ArticleDetailSerializer,
                                   ArticleListSerializer)


@extend_schema(
    tags=["content"],
    summary="List news and articles",
    description=("Only published items (`published_at` set and in the past) "
                 "are ever returned. Filter with `?type=news|article|blog`."),
)
class ArticleListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ArticleListSerializer
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter,
                       drf_filters.OrderingFilter]
    filterset_fields = ["type"]
    search_fields = ["title", "body"]
    ordering_fields = ["published_at", "title"]
    ordering = ["-published_at"]

    def get_queryset(self):
        return published_articles()


@extend_schema(tags=["content"], summary="Retrieve an article by slug")
class ArticleDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ArticleDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return published_articles()
