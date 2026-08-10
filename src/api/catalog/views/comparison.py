from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts import compare_services
from apps.catalog.models import Product
from apps.catalog.selectors import product_detail_queryset

from ..serializers.comparison import (ComparisonAttributeRowSerializer,
                                     ComparisonRequestSerializer)
from ..serializers.product import ProductDetailSerializer


def _comparison_payload(products, request) -> dict:
    return {
        "count": len(products),
        "products": ProductDetailSerializer(
            products, many=True, context={"request": request}).data,
        "attributes": compare_services.comparison_matrix(products),
    }


@extend_schema(
    tags=["catalog"],
    summary="Compare products ad hoc",
    description=(
        "Stateless comparison — nothing is written to the database. Returns "
        "the products plus an attribute matrix where rows shared by every "
        "product are listed first (`is_common: true`)."
    ),
    request=ComparisonRequestSerializer,
)
class ProductComparisonView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ComparisonRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_ids = compare_services.validate_comparison_ids(
            serializer.validated_data["product_ids"])

        products = list(product_detail_queryset().filter(id__in=product_ids))
        found = {p.id for p in products}
        missing = [pid for pid in product_ids if pid not in found]
        if missing:
            return Response(
                {"product_ids": [f"Unknown product id(s): {missing}."]},
                status=status.HTTP_400_BAD_REQUEST)

        order = {pid: i for i, pid in enumerate(product_ids)}
        products.sort(key=lambda p: order[p.id])
        return Response(_comparison_payload(products, request))


@extend_schema(
    tags=["catalog"],
    summary="Saved comparison list",
    responses=ComparisonAttributeRowSerializer(many=True),
    description=("Persisted comparison, scoped to the logged-in user or to "
                 "the guest session key."),
)
class CompareListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ids = list(compare_services.compare_queryset(request)
                   .values_list("product_id", flat=True))
        products = list(product_detail_queryset().filter(id__in=ids))
        return Response(_comparison_payload(products, request))

    def delete(self, request):
        compare_services.clear_compare(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["catalog"], summary="Add a product to the comparison",
               request=None, responses={201: ComparisonRequestSerializer})
class CompareAddView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, product_id):
        product = Product.objects.filter(
            pk=product_id, is_active=True).first()
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        compare_services.add_to_compare(request, product)
        return Response({"detail": "Added to comparison."},
                        status=status.HTTP_201_CREATED)


@extend_schema(tags=["catalog"], summary="Remove a product from the comparison",
               request=None, responses={204: None})
class CompareRemoveView(APIView):
    permission_classes = [AllowAny]

    def delete(self, request, product_id):
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        compare_services.remove_from_compare(request, product)
        return Response(status=status.HTTP_204_NO_CONTENT)
