from rest_framework import serializers

from apps.leads.models import Lead


class LeadCreateSerializer(serializers.ModelSerializer):
    """
    Write-only intake for site forms.

    ``status`` is not exposed: it is internal workflow state and a submitter
    must not be able to set it.
    """

    class Meta:
        model = Lead
        fields = ("id", "type", "name", "phone", "product", "consent")
        extra_kwargs = {"id": {"read_only": True}}

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                "Name must be at least 2 characters.")
        return cleaned

    def validate_phone(self, value: str) -> str:
        digits = [c for c in value if c.isdigit()]
        if len(digits) < 7:
            raise serializers.ValidationError(
                "Enter a valid phone number.")
        return value.strip()

    def validate_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                "Consent to be contacted is required.")
        return value
