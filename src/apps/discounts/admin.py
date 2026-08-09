from django.contrib import admin

from .models import DiscountTier, PromoCode


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'type', 'value', 'min_order',
                    'valid_to', 'usage_limit', 'used_count')
    list_filter = ('type',)
    search_fields = ('code',)
    readonly_fields = ('used_count',)


@admin.register(DiscountTier)
class DiscountTierAdmin(admin.ModelAdmin):
    list_display = ('id', 'threshold', 'percent', 'is_active')
    list_editable = ('percent', 'is_active')
    list_filter = ('is_active',)
