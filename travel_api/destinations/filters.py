"""Custom FilterSet for advanced destination search."""
from django_filters import rest_framework as filters

from .models import Destination


class DestinationFilter(filters.FilterSet):
    """
    Advanced destination filtering: exact-choice filters plus a derived
    budget_range filter that maps onto avg_daily_cost bands.
    """
    climate = filters.MultipleChoiceFilter(choices=Destination.ClimateChoices.choices)
    category = filters.MultipleChoiceFilter(choices=Destination.CategoryChoices.choices)
    min_cost = filters.NumberFilter(field_name='avg_daily_cost', lookup_expr='gte')
    max_cost = filters.NumberFilter(field_name='avg_daily_cost', lookup_expr='lte')
    budget_range = filters.CharFilter(method='filter_by_budget')

    class Meta:
        model = Destination
        fields = ['country', 'category', 'climate', 'is_active']

    def filter_by_budget(self, queryset, name, value):
        """Map a friendly 'budget' / 'moderate' / 'luxury' label onto a cost range."""
        if value == 'budget':
            return queryset.filter(avg_daily_cost__lt=100)
        if value == 'moderate':
            return queryset.filter(avg_daily_cost__gte=100, avg_daily_cost__lt=250)
        if value == 'luxury':
            return queryset.filter(avg_daily_cost__gte=250)
        return queryset
