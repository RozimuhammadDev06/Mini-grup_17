from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from ..serializers.profile import ProfileSerializer


@extend_schema(
    tags=["user"],
    summary="Retrieve or update the caller's profile",
    description=("The object is always resolved from `request.user`; there is "
                 "no id in the URL, so one account can never read or write "
                 "another's profile. Privileged fields are not writable."),
)
class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_object(self):
        return self.request.user
