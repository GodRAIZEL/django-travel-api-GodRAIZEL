"""Serializers for reviews."""
from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Full review serializer. Read-heavy fields (username, subject_name) are
    denormalized in via SerializerMethodField so list responses don't need
    a second round trip to identify who wrote what about what.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    subject_name = serializers.SerializerMethodField()
    subject_type = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'username', 'destination', 'accommodation', 'activity',
            'subject_name', 'subject_type', 'rating', 'title', 'content', 'visit_date',
            'images', 'helpful_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'helpful_count', 'created_at', 'updated_at']
        extra_kwargs = {
            'rating': {'help_text': 'Star rating from 1 (worst) to 5 (best).'},
            'visit_date': {'help_text': 'Date you actually visited/used this - cannot be in the future.'},
            'content': {'help_text': 'The body of the review.'},
            'destination': {'help_text': 'Set this OR accommodation OR activity - exactly one is required.'},
        }

    def get_subject_name(self, obj):
        subject = obj.subject
        return getattr(subject, 'name', str(subject)) if subject else None

    def get_subject_type(self, obj):
        if obj.destination_id:
            return 'destination'
        if obj.accommodation_id:
            return 'accommodation'
        if obj.activity_id:
            return 'activity'
        return None

    def validate(self, attrs):
        destination = attrs.get('destination')
        accommodation = attrs.get('accommodation')
        activity = attrs.get('activity')
        set_count = sum(1 for target in [destination, accommodation, activity] if target)
        if set_count != 1:
            raise serializers.ValidationError(
                'A review must reference exactly one of: destination, accommodation, or activity.'
            )
        return attrs

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value

    def validate_visit_date(self, value):
        from django.utils import timezone
        if value > timezone.now().date():
            raise serializers.ValidationError('Visit date cannot be in the future.')
        return value
