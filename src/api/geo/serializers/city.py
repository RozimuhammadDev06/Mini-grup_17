from rest_framework import serializers

from apps.geo.models import City


class CitySerializer(serializers.ModelSerializer):
    region = serializers.CharField(source="region.name", read_only=True)
    delivery_cost = serializers.DecimalField(
        source="delivery_zone.base_cost", max_digits=12, decimal_places=2,
        read_only=True)

    class Meta:
        model = City
        fields = ("id", "name", "region", "delivery_cost")
        read_only_fields = fields
