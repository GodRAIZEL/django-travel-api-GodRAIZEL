"""Read-only browsing of the audit trail, scoped to what the user is allowed to see."""
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.filters import OrderingFilter

from itineraries.models import Itinerary

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET-only access to activity log entries: either the user's own actions,
    or any action logged against an itinerary they own/collaborate on.
    """
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['action', 'itinerary']
    ordering_fields = ['created_at']

    def get_queryset(self):
        user = self.request.user
        visible_itineraries = Itinerary.objects.filter(Q(owner=user) | Q(collaborators=user))
        return ActivityLog.objects.filter(
            Q(user=user) | Q(itinerary__in=visible_itineraries)
        ).select_related('user', 'itinerary').distinct()
