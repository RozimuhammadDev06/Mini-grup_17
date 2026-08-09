from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'author_name', 'user',
                    'rating', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('is_published', 'rating', 'created_at')
    search_fields = ('author_name', 'comment', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at',)
