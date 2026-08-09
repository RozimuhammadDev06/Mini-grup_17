from django.contrib import admin

from .models import Article, Banner, Faq, Promotion, StaticPage


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'type', 'published_at')
    list_filter = ('type', 'published_at')
    search_fields = ('title', 'slug', 'body')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'discount_label', 'valid_until', 'category')
    list_filter = ('category', 'valid_until')
    search_fields = ('title', 'slug', 'body')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ('category',)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'link', 'sort')
    list_editable = ('sort',)
    search_fields = ('title',)


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'sort')
    list_editable = ('sort',)
    search_fields = ('question', 'answer')


@admin.register(StaticPage)
class StaticPageAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'slug')
    search_fields = ('title', 'slug', 'body')
    prepopulated_fields = {'slug': ('title',)}
