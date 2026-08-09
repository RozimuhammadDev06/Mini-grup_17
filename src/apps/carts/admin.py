from django.contrib import admin

from .models import Cart, CartItem, Compare, Wishlist


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ('product',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'promo_code', 'updated_at')
    search_fields = ('user__email', 'session_key')
    autocomplete_fields = ('user', 'promo_code')
    inlines = (CartItemInline,)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product')
    search_fields = ('user__email', 'product__name', 'product__article')
    autocomplete_fields = ('user', 'product')


@admin.register(Compare)
class CompareAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'product', 'category')
    list_filter = ('category',)
    search_fields = ('user__email', 'session_key', 'product__name')
    autocomplete_fields = ('user', 'product', 'category')
