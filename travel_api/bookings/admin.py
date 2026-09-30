from django.contrib import admin

from .models import Accommodation, Activity, Booking


@admin.register(Accommodation)
class AccommodationAdmin(admin.ModelAdmin):
    list_display = ['name', 'destination', 'accommodation_type', 'price_per_night', 'is_available']
    list_filter = ['accommodation_type', 'is_available']
    search_fields = ['name']


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['name', 'destination', 'category', 'price', 'is_available']
    list_filter = ['category', 'is_available']
    search_fields = ['name']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'itinerary', 'status', 'price', 'created_at']
    list_filter = ['status']
    search_fields = ['confirmation_code']
