from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'name', 'phone',
                    'product', 'status', 'consent', 'created_at')
    list_editable = ('status',)
    list_filter = ('type', 'status', 'consent', 'created_at')
    search_fields = ('name', 'phone', 'product__name', 'product__article')
    autocomplete_fields = ('product',)
    readonly_fields = ('created_at',)
