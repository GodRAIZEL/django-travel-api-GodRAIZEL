"""Serializers for the Destination model - separate list/detail shapes."""
from rest_framework import serializers

from .models import Destination


class DestinationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer used for list/browse views."""
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.SerializerMethodField()
    budget_tier = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = [
            'id', 'name', 'country', 'category', 'climate',
            'avg_daily_cost', 'image', 'average_rating', 'review_count', 'budget_tier',
        ]
        read_only_fields = ['id']

    def get_review_count(self, obj):
        return obj.reviews.count()

    def get_budget_tier(self, obj):
        return obj.budget_tier()


class DestinationDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested/derived data for the detail view."""
    average_rating = serializers.ReadOnlyField()
    total_itineraries = serializers.SerializerMethodField()
    top_activities = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_itineraries(self, obj):
        return obj.itineraries.count()

    def get_top_activities(self, obj):
        # Local import avoids a circular import at module load time
        # (bookings imports nothing from destinations at import time, but
        # keeping the import local documents the intentional one-way
        # dependency: destinations -> bookings serializers, never back).
        from bookings.serializers import ActivitySerializer
        activities = obj.activities.filter(is_available=True)[:5]
        return ActivitySerializer(activities, many=True, context=self.context).data

    def to_representation(self, instance):
        """Ensure image field renders an absolute URL when a request is available."""
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if request and instance.image:
            representation['image'] = request.build_absolute_uri(instance.image.url)
        return representation


class DestinationWriteSerializer(serializers.ModelSerializer):
    """Separate serializer used for create/update (admin) operations."""

    class Meta:
        model = Destination
        fields = [
            'name', 'country', 'description', 'category', 'climate',
            'best_time_to_visit', 'avg_daily_cost', 'image',
            'latitude', 'longitude', 'is_active',
        ]
        extra_kwargs = {
            'name': {'help_text': 'Unique display name for the destination, e.g. "Cape Town".'},
            'avg_daily_cost': {'help_text': 'Typical cost per day for one traveler, used to compute the budget tier.'},
            'category': {'help_text': 'One of beach, mountain, city, cultural, adventure, or relaxation.'},
        }

    def validate_avg_daily_cost(self, value):
        if value < 0:
            raise serializers.ValidationError('Average daily cost cannot be negative.')
        return value

    def validate_name(self, value):
        qs = Destination.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A destination with this name already exists.')
        return value
