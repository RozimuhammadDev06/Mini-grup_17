from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.content.selectors import HOME_CACHE_KEY, home_sections

from ..serializers.home import HomeSerializer


@extend_schema(
    tags=["content"],
    summary="Aggregated home-page payload",
    description=(
        "Everything the landing page needs in one request: banners, root "
        "categories, popular / best-selling / new / discounted / featured "
        "products, active promotions and the latest news — up to 10 items per "
        "section.\n\n"
        "Each section is a single query with subquery-based aggregates (no "
        "N+1), and the serialised payload is cached in Redis for "
        "`CACHE_TTL_MEDIUM` seconds. The cache holds no user-specific data."
    ),
    responses=HomeSerializer,
)
class HomeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get(HOME_CACHE_KEY)
        if cached is not None:
            return Response(cached)

        payload = HomeSerializer(
            home_sections(request), context={"request": request}).data
        cache.set(HOME_CACHE_KEY, payload, settings.CACHE_TTL_MEDIUM)
        return Response(payload)
