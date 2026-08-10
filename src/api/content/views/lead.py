from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..serializers.lead import LeadCreateSerializer


@extend_schema(
    tags=["content"],
    summary="Submit a lead (callback, price request, one-click buy)",
    description=(
        "Public, write-only intake for site forms. Leads are never readable "
        "through the public API — managers read them via the admin API or "
        "Django admin. Consent is mandatory."
    ),
    request=LeadCreateSerializer,
    responses={201: LeadCreateSerializer},
)
class LeadCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = LeadCreateSerializer
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Thank you. We will contact you shortly.",
             "id": serializer.instance.pk},
            status=status.HTTP_201_CREATED)
