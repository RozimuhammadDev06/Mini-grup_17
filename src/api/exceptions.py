"""
Project-wide API error handling.

Every error leaves the API in one of two shapes:

    {"detail": "Product not found."}                  # non-field errors
    {"email": ["Enter a valid email address."]}       # field validation

Unhandled exceptions are logged and returned as a generic 500 so that no
stack trace or internal message reaches the client.
"""

import logging
from typing import Any, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

GENERIC_SERVER_ERROR = "Internal server error."


def _normalise(data: Any) -> Any:
    """Guarantee a JSON object at the top level of every error response."""
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"detail": data}
    return {"detail": str(data)}


def api_exception_handler(exc: Exception, context: dict) -> Optional[Response]:
    """DRF ``EXCEPTION_HANDLER`` hook."""
    if isinstance(exc, DjangoValidationError):
        # Model/full_clean errors would otherwise surface as a 500.
        detail = exc.message_dict if hasattr(exc, "message_dict") \
            else {"detail": list(exc.messages)}
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)

    response = drf_exception_handler(exc, context)

    if response is None:
        view = context.get("view")
        request = context.get("request")
        logger.exception(
            "Unhandled exception in %s (%s %s)",
            view.__class__.__name__ if view else "unknown view",
            getattr(request, "method", "?"),
            getattr(request, "path", "?"),
        )
        return Response(
            {"detail": GENERIC_SERVER_ERROR},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response.data = _normalise(response.data)
    return response
