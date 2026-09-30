from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'rating', 'subject', 'visit_date', 'helpful_count']
    list_filter = ['rating']
    search_fields = ['title', 'content', 'user__username']
