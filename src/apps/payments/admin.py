from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'provider', 'provider_id',
                    'payment_type', 'status', 'amount')
    list_filter = ('provider', 'payment_type', 'status')
    search_fields = ('order__number', 'provider_id')
    autocomplete_fields = ('order',)
