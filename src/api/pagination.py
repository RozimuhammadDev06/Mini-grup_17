import math

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPagination(PageNumberPagination):
    """Default pagination: the standard DRF envelope plus a page count."""

    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data, **kwargs):
        return Response({
            "count": self.page.paginator.count,
            "pages": math.ceil(
                self.page.paginator.count / self.page.paginator.per_page),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            **kwargs,
            "results": data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "example": 123},
                "pages": {"type": "integer", "example": 7},
                "next": {"type": "string", "nullable": True,
                         "format": "uri"},
                "previous": {"type": "string", "nullable": True,
                             "format": "uri"},
                "results": schema,
            },
        }


class ItemPagination(CustomPagination):
    page_size = 10


class ObjectPaginationClass(CustomPagination):
    page_size = 10
