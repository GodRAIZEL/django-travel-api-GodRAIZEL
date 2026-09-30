from django.contrib import admin

from .models import Collaboration, DailyPlan, Itinerary


class DailyPlanInline(admin.TabularInline):
    model = DailyPlan
    extra = 0


class CollaborationInline(admin.TabularInline):
    model = Collaboration
    extra = 0


@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ['title', 'destination', 'owner', 'status', 'start_date', 'end_date', 'budget']
    list_filter = ['status', 'is_public']
    search_fields = ['title', 'owner__username']
    inlines = [DailyPlanInline, CollaborationInline]
