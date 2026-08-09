from django.contrib import admin

from .models import City, DeliveryZone, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'base_cost', 'per_kg')
    search_fields = ('name',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'delivery_zone')
    list_filter = ('region', 'delivery_zone')
    search_fields = ('name',)
    autocomplete_fields = ('region', 'delivery_zone')
