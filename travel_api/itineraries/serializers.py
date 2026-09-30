"""Serializers for Itinerary, Collaboration and DailyPlan."""
from rest_framework import serializers

from destinations.models import Destination
from destinations.serializers import DestinationListSerializer

from .models import Collaboration, DailyPlan, Itinerary


class CollaborationSerializer(serializers.ModelSerializer):
    """Serializer for the Itinerary <-> User through model."""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Collaboration
        fields = ['id', 'user', 'username', 'email', 'role', 'invited_at']
        read_only_fields = ['id', 'invited_at']


class DailyPlanSerializer(serializers.ModelSerializer):
    """Serializer for a single day's plan, with a computed activity count."""
    activities_count = serializers.SerializerMethodField()

    class Meta:
        model = DailyPlan
        fields = ['id', 'itinerary', 'day_number', 'date', 'title', 'notes', 'activities', 'activities_count']
        read_only_fields = ['id']

    def get_activities_count(self, obj):
        return obj.activities.count()

    def validate(self, attrs):
        itinerary = attrs.get('itinerary', getattr(self.instance, 'itinerary', None))
        day_date = attrs.get('date', getattr(self.instance, 'date', None))
        if itinerary and day_date and not (itinerary.start_date <= day_date <= itinerary.end_date):
            raise serializers.ValidationError({'date': "Day's date must fall within the itinerary's date range."})
        return attrs


class ItineraryBaseSerializer(serializers.ModelSerializer):
    """
    Base serializer shared by the list and detail serializers below - holds
    the read-only computed fields common to both.
    """
    duration_days = serializers.ReadOnlyField()
    budget_remaining = serializers.ReadOnlyField()

    class Meta:
        model = Itinerary
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class ItineraryListSerializer(ItineraryBaseSerializer):
    """Lightweight serializer for list views."""
    destination_name = serializers.CharField(source='destination.name', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta(ItineraryBaseSerializer.Meta):
        fields = [
            'id', 'title', 'destination', 'destination_name', 'owner', 'owner_username',
            'start_date', 'end_date', 'duration_days', 'budget', 'budget_remaining',
            'status', 'is_public',
        ]


class ItineraryDetailSerializer(ItineraryBaseSerializer):
    """
    Full serializer with nested destination, daily plans and collaborations.
    Auto-creates a Budget record whenever a new itinerary is created.
    """
    destination = DestinationListSerializer(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(
        queryset=Destination.objects.all(), source='destination', write_only=True
    )
    daily_plans = DailyPlanSerializer(many=True, read_only=True)
    collaborations = CollaborationSerializer(many=True, read_only=True)
    bookings_count = serializers.SerializerMethodField()

    class Meta(ItineraryBaseSerializer.Meta):
        fields = [
            'id', 'title', 'description', 'destination', 'destination_id', 'owner',
            'start_date', 'end_date', 'duration_days', 'budget', 'actual_spent',
            'budget_remaining', 'status', 'is_public', 'itinerary_pdf',
            'daily_plans', 'collaborations', 'bookings_count', 'created_at', 'updated_at',
        ]

    def get_bookings_count(self, obj):
        return obj.bookings.count()

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})
        budget = attrs.get('budget', getattr(self.instance, 'budget', None))
        if budget is not None and budget < 0:
            raise serializers.ValidationError({'budget': 'Budget must be positive.'})
        return attrs

    def create(self, validated_data):
        itinerary = Itinerary.objects.create(**validated_data)
        # Local import: budgets app is only needed here, avoids a hard
        # module-level dependency of itineraries on budgets.
        from budgets.models import Budget
        Budget.objects.get_or_create(itinerary=itinerary)
        return itinerary

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if request and instance.itinerary_pdf:
            representation['itinerary_pdf'] = request.build_absolute_uri(instance.itinerary_pdf.url)
        return representation


class ItineraryCreateUpdateSerializer(serializers.ModelSerializer):
    """Separate, minimal serializer used specifically for create/update payloads."""

    class Meta:
        model = Itinerary
        fields = ['title', 'description', 'destination', 'start_date', 'end_date', 'budget', 'is_public']
        extra_kwargs = {
            'title': {'help_text': 'A short, human-readable name for the trip, e.g. "Rome Adventure".'},
            'description': {'help_text': 'Optional free-text notes about the trip.'},
            'destination': {'help_text': 'ID of the Destination this itinerary is built around.'},
            'start_date': {'help_text': 'First day of the trip (YYYY-MM-DD).'},
            'end_date': {'help_text': 'Last day of the trip (YYYY-MM-DD); must not be before start_date.'},
            'budget': {'help_text': 'Total planned spend for the whole trip, in the account currency.'},
            'is_public': {'help_text': 'If true, this itinerary is visible to other users browsing public trips.'},
        }

    def validate_budget(self, value):
        if value <= 0:
            raise serializers.ValidationError('Budget must be greater than zero.')
        return value

    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})
        return attrs
