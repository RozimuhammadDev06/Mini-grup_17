"""Liveness/readiness probe used by the Docker healthchecks."""

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    checks = serializers.DictField(child=serializers.CharField())


@extend_schema(
    tags=["ops"],
    summary="Health check",
    description=("Reports database and cache reachability. Returns 503 when "
                 "a dependency is down so orchestrators stop routing here."),
    responses=HealthSerializer,
)
class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        checks = {"database": "ok", "cache": "ok"}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            checks["database"] = f"error: {exc.__class__.__name__}"

        try:
            cache.set("healthz", "1", 5)
            if cache.get("healthz") != "1":
                checks["cache"] = "error: value mismatch"
        except Exception as exc:
            checks["cache"] = f"error: {exc.__class__.__name__}"

        healthy = all(value == "ok" for value in checks.values())
        return Response(
            {"status": "ok" if healthy else "degraded", "checks": checks},
            status=status.HTTP_200_OK if healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
