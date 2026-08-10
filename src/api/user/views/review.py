from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.orders.services import has_purchased
from apps.reviews.models import Review

from ..permissions import IsOwner
from ..serializers.review import MyReviewSerializer

# Reviews are gated to verified buyers. Flip to False to allow any
# authenticated user to review any product.
REQUIRE_VERIFIED_PURCHASE = True


@extend_schema(tags=["user"])
class MyReviewViewSet(ModelViewSet):
    """
    CRUD over the caller's own reviews.

    The queryset is scoped to ``request.user``, so PATCH/DELETE against
    another user's review id returns 404 rather than modifying it.
    """

    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = MyReviewSerializer
    queryset = Review.objects.none()

    def get_queryset(self):
        return (Review.objects
                .filter(user=self.request.user)
                .select_related("product"))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data.get("product")

        if product is None:
            return Response({"product": ["This field is required."]},
                            status=status.HTTP_400_BAD_REQUEST)

        if Review.objects.filter(
                user=request.user, product=product).exists():
            return Response(
                {"product": ["You have already reviewed this product."]},
                status=status.HTTP_400_BAD_REQUEST)

        if REQUIRE_VERIFIED_PURCHASE and not has_purchased(
                request.user, product.pk):
            return Response(
                {"product": ["You can only review products you have "
                             "purchased."]},
                status=status.HTTP_403_FORBIDDEN)

        serializer.save(
            user=request.user,
            author_name=serializer.validated_data.get("author_name")
            or request.user.full_name.strip() or request.user.email,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        # An edited review goes back into moderation.
        serializer.save(is_published=False)
