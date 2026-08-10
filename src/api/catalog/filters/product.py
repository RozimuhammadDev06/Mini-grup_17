import django_filters as filters
from django.db.models import F, Q

from apps.catalog.models import Brand, Category, Product


class ProductFilter(filters.FilterSet):
    """
    Composable storefront filters. Every parameter can be combined with any
    other; each one narrows the queryset independently.

    ``min_price``/``max_price`` and ``price_min``/``price_max`` are accepted
    as synonyms because both spellings appear in the frontend brief.
    """

    category = filters.ModelMultipleChoiceFilter(
        queryset=Category.objects.all(), method="filter_category",
        help_text="Category id. Includes products of descendant categories.")
    category_slug = filters.CharFilter(
        field_name="category__slug", lookup_expr="iexact")
    brand = filters.ModelMultipleChoiceFilter(
        queryset=Brand.objects.all(), field_name="brand")
    brand_slug = filters.CharFilter(
        field_name="brand__slug", lookup_expr="iexact")

    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    price_min = filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = filters.NumberFilter(field_name="price", lookup_expr="lte")

    stock = filters.BooleanFilter(
        method="filter_stock", help_text="true = in stock only.")
    in_stock = filters.BooleanFilter(method="filter_stock")
    discount = filters.BooleanFilter(
        method="filter_discount", help_text="true = discounted products only.")
    featured = filters.BooleanFilter(field_name="is_featured")
    rating = filters.NumberFilter(
        method="filter_rating", help_text="Minimum average rating.")

    created_after = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte")

    attribute = filters.CharFilter(
        method="filter_attribute",
        help_text=("Repeatable. `attribute=code:value`, e.g. "
                   "`attribute=power:1500`. Repeating the same code ORs the "
                   "values; different codes AND together."))

    class Meta:
        model = Product
        fields = ("category", "brand", "featured")

    def filter_category(self, queryset, name, value):
        if not value:
            return queryset
        ids = set()
        for category in value:
            ids.add(category.pk)
            ids.update(category.children.values_list("pk", flat=True))
        return queryset.filter(category_id__in=ids)

    def filter_stock(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset.filter(
            Q(stock__isnull=True) | Q(stock__quantity__lte=0))

    def filter_discount(self, queryset, name, value):
        if value is None:
            return queryset
        condition = Q(old_price__isnull=False, old_price__gt=F("price"))
        return queryset.filter(condition) if value \
            else queryset.exclude(condition)

    def filter_rating(self, queryset, name, value):
        if value in (None, ""):
            return queryset
        return queryset.filter(rating__gte=value)

    def filter_attribute(self, queryset, name, value):
        """Each `code:value` pair narrows further, so filters intersect."""
        raw_values = self.data.getlist("attribute") \
            if hasattr(self.data, "getlist") else [value]

        grouped: dict[str, list[str]] = {}
        for raw in raw_values:
            if not raw or ":" not in raw:
                continue
            code, _, val = raw.partition(":")
            grouped.setdefault(code.strip(), []).append(val.strip())

        for code, values in grouped.items():
            queryset = queryset.filter(
                Q(product_attributes__attribute__code__iexact=code)
                & (Q(product_attributes__value__value_string__in=values)
                   | Q(product_attributes__value_number__in=[
                       v for v in values if _is_number(v)] or [None]))
            )
        return queryset.distinct()


def _is_number(value: str) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
