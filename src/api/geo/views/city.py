from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from apps.geo.selectors import deliverable_cities

from ..serializers.city import CitySerializer


@extend_schema(
    tags=["geo"],
    summary="Cities the store delivers to",
    description=(
        "Each city's `id` is the `city_id` checkout requires for delivery, "
        "and `delivery_cost` is what that delivery adds to the order. "
        "Cities without a delivery zone are not listed and cannot be "
        "delivered to. Filter with `?region=<id>` or `?search=<name>`."
    ),
)
class CityListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CitySerializer
    pagination_class = None
    filterset_fields = ["region"]
    search_fields = ["name", "region__name"]

    def get_queryset(self):
        return deliverable_cities()
