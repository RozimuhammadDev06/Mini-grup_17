from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.content.selectors import banners, faqs
from apps.content.models import StaticPage

from ..serializers.banner import BannerSerializer
from ..serializers.faq import FaqSerializer
from ..serializers.page import StaticPageSerializer


@extend_schema(tags=["content"], summary="List banners, ordered by sort")
class BannerListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BannerSerializer
    pagination_class = None

    def get_queryset(self):
        return banners()


@extend_schema(tags=["content"], summary="List FAQ entries")
class FaqListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = FaqSerializer
    pagination_class = None

    def get_queryset(self):
        return faqs()


@extend_schema(tags=["content"], summary="Retrieve a static page by slug")
class StaticPageDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = StaticPageSerializer
    lookup_field = "slug"
    queryset = StaticPage.objects.all()
