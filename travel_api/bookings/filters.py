"""Custom FilterSets for bookings-related querysets."""
from django_filters import rest_framework as filters

from .models import Booking


class BookingFilter(filters.FilterSet):
    """Filter bookings by status, date range and booking type."""
    booking_date_after = filters.DateFilter(field_name='booking_date', lookup_expr='gte')
    booking_date_before = filters.DateFilter(field_name='booking_date', lookup_expr='lte')
    has_accommodation = filters.BooleanFilter(field_name='accommodation', lookup_expr='isnull', exclude=True)

    class Meta:
        model = Booking
        fields = ['status', 'itinerary']
