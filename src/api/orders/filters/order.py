import django_filters as filters

from apps.orders.models import Order


class OrderFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Order.Status.choices)
    created_after = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Order
        fields = ("status", "delivery_type", "payment_method")
