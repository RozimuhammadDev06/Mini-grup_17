from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "provider_id", "payment_type",
                    "status", "amount", "created_at")
    list_filter = ("provider", "payment_type", "status", "created_at")
    search_fields = ("order__number", "provider_id")
    autocomplete_fields = ("order",)
    readonly_fields = ("merchant_prepare_id", "merchant_confirm_id",
                       "raw_response", "created_at", "updated_at")
    date_hierarchy = "created_at"
