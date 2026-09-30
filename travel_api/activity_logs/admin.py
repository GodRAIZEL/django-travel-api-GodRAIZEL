from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'itinerary', 'created_at']
    list_filter = ['action']
    search_fields = ['description']
    readonly_fields = [f.name for f in ActivityLog._meta.fields]
