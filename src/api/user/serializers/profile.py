from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    """
    The user's own profile.

    Privileged columns (``is_staff``, ``is_superuser``, ``is_active``,
    ``groups``, ``user_permissions``, ``password``, ``email``) are absent
    from ``fields`` entirely, so they cannot be mass-assigned. Email changes
    go through the verified change-email flow instead.
    """

    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name",
                  "phone_number", "language", "region", "date_joined",
                  "is_active")
        read_only_fields = ("id", "email", "full_name", "date_joined",
                            "is_active")

    def validate_first_name(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError(
                "First name must be at least 2 characters.")
        return value.strip()
