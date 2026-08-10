from rest_framework import serializers

from apps.users.models import Address


class AddressSerializer(serializers.ModelSerializer):
    """
    ``user`` is intentionally not a field: the owner comes from
    ``request.user`` in the view, so a client cannot create or move an
    address into another account.
    """

    class Meta:
        model = Address
        fields = ("id", "company_name", "region", "city", "street", "house",
                  "phone", "is_default")

    def validate(self, attrs: dict) -> dict:
        merged = {**getattr(self.instance, "__dict__", {}), **attrs}
        if not (merged.get("city") or "").strip():
            raise serializers.ValidationError({"city": ["City is required."]})
        if not (merged.get("street") or "").strip():
            raise serializers.ValidationError(
                {"street": ["Street is required."]})
        if not (merged.get("phone") or "").strip():
            raise serializers.ValidationError(
                {"phone": ["Phone is required."]})
        return attrs
