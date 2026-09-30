"""Review model: user ratings/comments on destinations, accommodations, or activities."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """
    A user's review of exactly one of: a destination, an accommodation, or
    an activity. Exactly one FK target must be set (enforced in clean()).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews'
    )
    destination = models.ForeignKey(
        'destinations.Destination', on_delete=models.CASCADE, related_name='reviews', null=True, blank=True
    )
    accommodation = models.ForeignKey(
        'bookings.Accommodation', on_delete=models.CASCADE, related_name='reviews', null=True, blank=True
    )
    activity = models.ForeignKey(
        'bookings.Activity', on_delete=models.CASCADE, related_name='reviews', null=True, blank=True
    )
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200)
    content = models.TextField()
    visit_date = models.DateField()
    images = models.JSONField(default=list, blank=True)
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['destination', 'rating']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.title} by {self.user.username}"

    def clean(self):
        targets = [self.destination_id, self.accommodation_id, self.activity_id]
        set_count = sum(1 for target in targets if target)
        if set_count != 1:
            raise ValidationError('A review must be for exactly one of: destination, accommodation, or activity.')

    def mark_helpful(self):
        """Business-logic helper: increment the helpful counter atomically."""
        from django.db.models import F
        Review.objects.filter(pk=self.pk).update(helpful_count=F('helpful_count') + 1)
        self.refresh_from_db(fields=['helpful_count'])
        return self.helpful_count

    @property
    def subject(self):
        """Return whichever object (destination/accommodation/activity) this review targets."""
        return self.destination or self.accommodation or self.activity
