from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.users.models import Address

from ..permissions import IsOwner
from ..serializers.address import AddressSerializer


@extend_schema(tags=["user"])
class AddressViewSet(ModelViewSet):
    """
    CRUD over the caller's delivery addresses.

    The queryset is filtered by ``request.user`` before any lookup, so another
    user's address id resolves to 404 rather than leaking its existence.
    """

    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = AddressSerializer
    pagination_class = None
    # Static queryset for schema introspection only; get_queryset()
    # below is what actually serves requests.
    queryset = Address.objects.none()

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Owner comes from the session, never from the request body.
        serializer.save(user=self.request.user)

    @extend_schema(summary="Make this address the default")
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        address = self.get_object()
        with transaction.atomic():
            Address.objects.filter(user=request.user).update(is_default=False)
            address.is_default = True
            address.save(update_fields=["is_default"])
        return Response(self.get_serializer(address).data,
                        status=status.HTTP_200_OK)
