"""Serializers for Accommodation, Activity and Booking."""
from django.db.models import Avg
from rest_framework import serializers

from .models import Accommodation, Activity, Booking


class AccommodationSerializer(serializers.ModelSerializer):
    """Full serializer for accommodations, including a computed review average."""
    average_rating = serializers.SerializerMethodField()
    destination_name = serializers.CharField(source='destination.name', read_only=True)

    class Meta:
        model = Accommodation
        fields = [
            'id', 'name', 'destination', 'destination_name', 'accommodation_type',
            'description', 'price_per_night', 'max_guests', 'amenities', 'address',
            'contact_email', 'contact_phone', 'image', 'is_available',
            'average_rating', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_average_rating(self, obj):
        # Prefer a value pre-computed by the viewset's annotate() to avoid an
        # extra query per row; fall back to a direct aggregate otherwise.
        if hasattr(obj, 'rating'):
            return round(obj.rating, 2) if obj.rating is not None else None
        result = obj.reviews.aggregate(avg=Avg('rating'))
        return round(result['avg'], 2) if result['avg'] is not None else None

    def validate_price_per_night(self, value):
        if value < 0:
            raise serializers.ValidationError('Price per night cannot be negative.')
        return value

    def validate_max_guests(self, value):
        if value < 1:
            raise serializers.ValidationError('An accommodation must allow at least one guest.')
        return value


class ActivitySerializer(serializers.ModelSerializer):
    """Full serializer for activities, with the destination name denormalized in for convenience."""
    destination_name = serializers.CharField(source='destination.name', read_only=True)
    booking_count = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            'id', 'name', 'destination', 'destination_name', 'category', 'description',
            'duration_hours', 'price', 'max_participants', 'requirements', 'image',
            'is_available', 'booking_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_booking_count(self, obj):
        return getattr(obj, 'booking_count', obj.bookings.count())

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError('Price cannot be negative.')
        return value

    def validate_duration_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError('Duration must be greater than zero.')
        return value


class BaseBookingSerializer(serializers.ModelSerializer):
    """
    Shared base for booking serializers. Concrete list/detail serializers
    extend this to avoid repeating field-level validation.
    """

    class Meta:
        model = Booking
        fields = [
            'id', 'user', 'itinerary', 'accommodation', 'activity', 'booking_date',
            'check_in', 'check_out', 'guests_count', 'price', 'status',
            'confirmation_code', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'status', 'confirmation_code', 'created_at', 'updated_at']

    def validate(self, attrs):
        accommodation = attrs.get('accommodation', getattr(self.instance, 'accommodation', None))
        activity = attrs.get('activity', getattr(self.instance, 'activity', None))
        if not accommodation and not activity:
            raise serializers.ValidationError('Booking must reference either an accommodation or an activity.')
        if accommodation and activity:
            raise serializers.ValidationError('Booking cannot reference both an accommodation and an activity.')
        check_in = attrs.get('check_in', getattr(self.instance, 'check_in', None))
        check_out = attrs.get('check_out', getattr(self.instance, 'check_out', None))
        if check_in and check_out and check_out < check_in:
            raise serializers.ValidationError({'check_out': 'Check-out date must be after check-in date.'})
        return attrs

    def validate_guests_count(self, value):
        if value < 1:
            raise serializers.ValidationError('At least one guest is required.')
        return value


class BookingListSerializer(BaseBookingSerializer):
    """Lightweight serializer for list views, extending the shared base."""
    accommodation_name = serializers.CharField(source='accommodation.name', read_only=True)
    activity_name = serializers.CharField(source='activity.name', read_only=True)

    class Meta(BaseBookingSerializer.Meta):
        fields = BaseBookingSerializer.Meta.fields + ['accommodation_name', 'activity_name']


class BookingDetailSerializer(BaseBookingSerializer):
    """
    Detail serializer, also extending the shared base, that computes the
    booking price automatically on create rather than trusting client input.
    """

    def create(self, validated_data):
        instance = Booking(**validated_data)
        instance.price = self._compute_price(instance)
        instance.full_clean()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.price = self._compute_price(instance)
        instance.full_clean()
        instance.save()
        return instance

    @staticmethod
    def _compute_price(booking):
        if booking.accommodation and booking.check_in and booking.check_out:
            nights = (booking.check_out - booking.check_in).days
            return booking.accommodation.nightly_total(nights) * booking.guests_count / max(booking.guests_count, 1)
        if booking.activity:
            return booking.activity.price * booking.guests_count
        return booking.price or 0

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['price'] = f"{float(representation['price']):.2f}"
        return representation
