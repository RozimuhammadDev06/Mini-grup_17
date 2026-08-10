from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts import compare_services
from apps.carts.models import Wishlist
from apps.catalog.models import Product

from ..serializers.wishlist import (WishlistAddSerializer, WishlistSerializer,
                                    WishlistStatusSerializer)


@extend_schema(tags=["user"], summary="List the caller's wishlist")
class WishlistListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistSerializer
    queryset = Wishlist.objects.none()

    def get_queryset(self):
        return compare_services.wishlist_queryset(self.request.user)


@extend_schema(
    tags=["user"],
    summary="Add a product to the wishlist",
    description=("Enforced by a unique (user, product) constraint — adding "
                 "the same product twice returns 400, never a duplicate row."),
    request=WishlistAddSerializer,
)
class WishlistAddView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistAddSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = Product.objects.filter(
            pk=serializer.validated_data["product_id"],
            is_active=True).first()
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        item = compare_services.add_to_wishlist(request.user, product)
        return Response(
            WishlistSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED)


@extend_schema(tags=["user"], summary="Remove a product from the wishlist",
               responses={204: None})
class WishlistItemView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        compare_services.remove_from_wishlist(request.user, product)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["user"],
    summary="Check whether a product is in the wishlist",
    responses=WishlistStatusSerializer,
)
class WishlistStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        return Response({
            "product_id": product_id,
            "in_wishlist": compare_services.is_in_wishlist(
                request.user, product_id),
        })
