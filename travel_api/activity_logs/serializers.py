"""Read-only serializer for the audit trail."""
from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    """Serializes an audit-trail entry; entries are created server-side only, never via the API."""
    username = serializers.CharField(source='user.username', read_only=True, default=None)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    itinerary_title = serializers.CharField(source='itinerary.title', read_only=True, default=None)

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'user', 'username', 'itinerary', 'itinerary_title',
            'action', 'action_display', 'description', 'metadata', 'created_at',
        ]
        read_only_fields = fields
