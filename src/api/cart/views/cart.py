from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.carts import services
from apps.catalog.models import Product

from ..serializers.cart import (AddCartItemSerializer, CartSerializer,
                                PromoCodeSerializer,
                                UpdateCartItemSerializer)


class CartContextMixin:
    """Resolves the cart from ``request.user`` or the guest session key."""

    permission_classes = [AllowAny]

    def get_cart(self):
        return services.resolve_cart(self.request)

    def cart_response(self, status_code=status.HTTP_200_OK):
        cart = self.get_cart()
        # Re-fetch through the join-optimised queryset before serialising.
        services.cart_items(cart)
        return Response(
            CartSerializer(cart, context={"request": self.request}).data,
            status=status_code)


def _get_product_or_404(product_id):
    return Product.objects.filter(
        pk=product_id, is_active=True).select_related("stock").first()


@extend_schema(
    tags=["cart"],
    summary="Retrieve the current cart",
    description=("Works for guests (identified by session cookie) and for "
                 "authenticated users. Totals are always recomputed on the "
                 "server; prices in the request body are ignored."),
    responses=CartSerializer,
)
class CartDetailView(CartContextMixin, APIView):
    def get(self, request):
        return self.cart_response()

    @extend_schema(tags=["cart"], summary="Empty the cart")
    def delete(self, request):
        services.clear(self.get_cart())
        return self.cart_response()


@extend_schema(
    tags=["cart"],
    summary="Add a product to the cart",
    description=("Quantity is added to any existing line. Rejected with 400 "
                 "if the resulting quantity exceeds available stock."),
    request=AddCartItemSerializer,
    responses=CartSerializer,
)
class CartAddItemView(CartContextMixin, GenericAPIView):
    serializer_class = AddCartItemSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = _get_product_or_404(
            serializer.validated_data["product_id"])
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        services.add_item(self.get_cart(), product,
                          serializer.validated_data["quantity"])
        return self.cart_response(status.HTTP_201_CREATED)


@extend_schema(
    tags=["cart"],
    summary="Set the quantity of a cart line",
    request=UpdateCartItemSerializer,
    responses=CartSerializer,
)
class CartItemView(CartContextMixin, GenericAPIView):
    serializer_class = UpdateCartItemSerializer

    def patch(self, request, product_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = _get_product_or_404(product_id)
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        services.set_quantity(self.get_cart(), product,
                              serializer.validated_data["quantity"])
        return self.cart_response()

    @extend_schema(tags=["cart"], summary="Remove a line from the cart")
    def delete(self, request, product_id):
        product = _get_product_or_404(product_id)
        if product is None:
            return Response({"detail": "Product not found."},
                            status=status.HTTP_404_NOT_FOUND)
        services.remove_item(self.get_cart(), product)
        return self.cart_response()


@extend_schema(
    tags=["cart"],
    summary="Apply a promo code",
    request=PromoCodeSerializer,
    responses=CartSerializer,
)
class CartPromoView(CartContextMixin, GenericAPIView):
    serializer_class = PromoCodeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.apply_promo_code(
            self.get_cart(), serializer.validated_data["code"])
        return self.cart_response()

    @extend_schema(tags=["cart"], summary="Remove the applied promo code")
    def delete(self, request):
        services.remove_promo_code(self.get_cart())
        return self.cart_response()
