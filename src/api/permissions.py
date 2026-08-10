"""Permission classes shared by every API audience."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwner(BasePermission):
    """
    Object belongs to the requesting user.

    A second line of defence only: every owner-scoped view must *also* filter
    its queryset by ``request.user``, so an object the user does not own is a
    404 rather than a 403 that confirms the row exists.
    """

    owner_field = "user"

    def has_object_permission(self, request, view, obj):
        owner_field = getattr(view, "owner_field", self.owner_field)
        return getattr(obj, f"{owner_field}_id", None) == request.user.id


class IsOwnerOrReadOnly(IsOwner):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return super().has_object_permission(request, view, obj)


class IsStaff(BasePermission):
    """Django staff flag — the gate for the whole admin API."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.is_staff)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
