from django.contrib import admin

from .models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    CategoryAttribute,
    Product,
    ProductAttribute,
    ProductImage,
    Stock,
)


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 0


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name', 'unit', 'type',
                    'is_filterable', 'is_comparable')
    list_filter = ('type', 'is_filterable', 'is_comparable')
    search_fields = ('code', 'name')
    inlines = (AttributeValueInline,)


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ('id', 'attribute', 'value_string', 'value_number')
    list_filter = ('attribute',)
    search_fields = ('value_string',)
    autocomplete_fields = ('attribute',)


class CategoryAttributeInline(admin.TabularInline):
    model = CategoryAttribute
    extra = 0
    autocomplete_fields = ('attribute',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'parent', 'sort', 'is_active')
    list_editable = ('sort', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('parent',)
    inlines = (CategoryAttributeInline,)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 0
    autocomplete_fields = ('attribute', 'value')


class StockInline(admin.StackedInline):
    model = Stock
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'name', 'category',
                    'brand', 'price', 'old_price', 'is_active')
    list_editable = ('price', 'is_active')
    list_filter = ('is_active', 'category', 'brand')
    search_fields = ('name', 'slug', 'article')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('category', 'brand')
    readonly_fields = ('created_at',)
    inlines = (ProductImageInline, ProductAttributeInline, StockInline)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'quantity', 'status', 'synced_at')
    list_filter = ('status',)
    search_fields = ('product__name', 'product__article')
    autocomplete_fields = ('product',)
