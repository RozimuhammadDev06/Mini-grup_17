from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ('product',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'user', 'status', 'delivery_type',
                    'payment_method', 'total', 'created_at', 'paid_at')
    list_editable = ('status',)
    list_filter = ('status', 'delivery_type', 'payment_method', 'created_at')
    search_fields = ('number', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    inlines = (OrderItemInline,)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'name_snapshot',
                    'article_snapshot', 'price', 'quantity')
    search_fields = ('order__number', 'name_snapshot', 'article_snapshot')
    autocomplete_fields = ('order', 'product')
