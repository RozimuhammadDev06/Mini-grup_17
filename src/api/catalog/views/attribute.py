from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from apps.catalog.models import Attribute, CategoryAttribute

from ..serializers.attribute import AttributeSerializer


@extend_schema(
    tags=["catalog"],
    summary="List filterable attributes",
    description=("Pass `?category=<id>` to get only the attributes configured "
                 "as filters for that category, in their configured order."),
)
class AttributeListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AttributeSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Attribute.objects.filter(
            is_filterable=True).prefetch_related("values")
        category_id = self.request.query_params.get("category")
        if category_id:
            ordered_ids = (CategoryAttribute.objects
                           .filter(category_id=category_id)
                           .order_by("sort")
                           .values_list("attribute_id", flat=True))
            qs = qs.filter(id__in=list(ordered_ids))
        return qs
