from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters as drf_filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.selectors import (product_detail_queryset, product_queryset,
                                    related_products)

from ..filters.product import ProductFilter
from ..serializers.product import (ProductDetailSerializer,
                                   ProductListSerializer)


@extend_schema(
    tags=["catalog"],
    summary="List products",
    description=(
        "Public, paginated product listing. All filters compose, e.g.\n\n"
        "`?category=1&min_price=100&max_price=1000&stock=true"
        "&ordering=-created_at&search=drill`\n\n"
        "`ordering` accepts `price`, `-price`, `created_at`, `-created_at`, "
        "`name`, `rating`, `-rating`, `sold_count`, `-sold_count`."
    ),
    parameters=[
        OpenApiParameter("search", str,
                         description="Matches name, article and description."),
    ],
)
class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter,
                       drf_filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "article", "description"]
    ordering_fields = ["price", "created_at", "name", "rating", "sold_count",
                       "review_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return product_queryset()


@extend_schema(
    tags=["catalog"],
    summary="Product detail",
    description=("Full product record including images, attributes, stock, "
                 "rating and review count."),
)
class ProductDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return product_detail_queryset()


@extend_schema(
    tags=["catalog"],
    summary="Product detail by id",
    responses=ProductDetailSerializer,
)
class ProductDetailByIdView(ProductDetailView):
    lookup_field = "pk"


@extend_schema(
    tags=["catalog"],
    summary="Related products",
    responses=ProductListSerializer(many=True),
)
class RelatedProductsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        product = product_queryset().filter(slug=slug).first()
        if product is None:
            return Response({"detail": "Product not found."}, status=404)
        products = related_products(product)
        return Response(ProductListSerializer(
            products, many=True, context={"request": request}).data)
