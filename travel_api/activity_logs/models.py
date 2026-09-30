"""Audit-trail model: a lightweight, append-only log of notable actions."""
from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """
    A single audit-trail entry. Deliberately generic (a free-text `action`
    plus `description`) rather than one FK per possible target, since the
    set of things worth logging (itinerary changes, collaborator changes,
    booking changes, expenses...) spans several apps and grows over time.
    `itinerary` is kept as an optional FK because most loggable events in
    this API happen in the context of a trip, which makes "show me
    everything that happened on this itinerary" a cheap, indexed query.
    """

    class ActionChoices(models.TextChoices):
        ITINERARY_CREATED = 'itinerary_created', 'Itinerary Created'
        ITINERARY_UPDATED = 'itinerary_updated', 'Itinerary Updated'
        ITINERARY_DELETED = 'itinerary_deleted', 'Itinerary Deleted'
        COLLABORATOR_ADDED = 'collaborator_added', 'Collaborator Added'
        COLLABORATOR_REMOVED = 'collaborator_removed', 'Collaborator Removed'
        BOOKING_CREATED = 'booking_created', 'Booking Created'
        BOOKING_CONFIRMED = 'booking_confirmed', 'Booking Confirmed'
        BOOKING_CANCELLED = 'booking_cancelled', 'Booking Cancelled'
        EXPENSE_ADDED = 'expense_added', 'Expense Added'
        REVIEW_POSTED = 'review_posted', 'Review Posted'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='activity_logs',
    )
    itinerary = models.ForeignKey(
        'itineraries.Itinerary', on_delete=models.CASCADE, null=True, blank=True,
        related_name='activity_logs',
    )
    action = models.CharField(max_length=30, choices=ActionChoices.choices)
    description = models.CharField(max_length=300)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['itinerary', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.get_action_display()} by {self.user_id} at {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def record(cls, *, user, action, description, itinerary=None, **metadata):
        """
        Business-logic helper: the single call site every view should use
        to write a log entry, so the shape stays consistent everywhere.
        """
        return cls.objects.create(
            user=user, action=action, description=description,
            itinerary=itinerary, metadata=metadata,
        )
