"""Itinerary planning models: Itinerary, Collaboration (M2M through), DailyPlan."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Itinerary(models.Model):
    """A user's trip plan for a given destination, with a status lifecycle."""

    class StatusChoices(models.TextChoices):
        PLANNING = 'planning', 'Planning'
        BOOKED = 'booked', 'Booked'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    destination = models.ForeignKey(
        'destinations.Destination', on_delete=models.PROTECT, related_name='itineraries'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_itineraries'
    )
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='Collaboration',
        related_name='shared_itineraries',
        blank=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    actual_spent = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PLANNING)
    is_public = models.BooleanField(default=False)
    itinerary_pdf = models.FileField(upload_to='itinerary_pdfs/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = 'Itineraries'
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.title} - {self.destination.name}"

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be after start date.'})
        if self.budget is not None and self.budget < 0:
            raise ValidationError({'budget': 'Budget must be positive.'})

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def budget_remaining(self):
        return self.budget - self.actual_spent

    def add_collaborator(self, user, role='viewer'):
        """Business-logic helper: add a user as a collaborator with the given role."""
        return Collaboration.objects.create(itinerary=self, user=user, role=role)

    def role_for(self, user):
        """Return the effective role a user has on this itinerary (owner/role/None)."""
        if user == self.owner:
            return 'owner'
        collaboration = self.collaborations.filter(user=user).first()
        return collaboration.role if collaboration else None


class Collaboration(models.Model):
    """Through model for Itinerary <-> User, carrying a per-user role."""

    class RoleChoices(models.TextChoices):
        VIEWER = 'viewer', 'Viewer'
        EDITOR = 'editor', 'Editor'
        ADMIN = 'admin', 'Admin'

    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='collaborations')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='collaborations'
    )
    role = models.CharField(max_length=10, choices=RoleChoices.choices, default=RoleChoices.VIEWER)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['itinerary', 'user']
        ordering = ['-invited_at']

    def __str__(self):
        return f"{self.user.username} - {self.itinerary.title} ({self.role})"

    def clean(self):
        if self.user_id and self.itinerary_id and self.user_id == self.itinerary.owner_id:
            raise ValidationError('The owner cannot also be added as a collaborator.')


class DailyPlan(models.Model):
    """A single day's plan within an itinerary, linking to a set of activities."""

    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='daily_plans')
    day_number = models.PositiveIntegerField()
    date = models.DateField()
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    activities = models.ManyToManyField(
        'bookings.Activity', related_name='daily_plans', blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day_number']
        unique_together = ['itinerary', 'day_number']

    def __str__(self):
        return f"Day {self.day_number}: {self.title}"

    def clean(self):
        if self.itinerary_id and self.date:
            if self.date < self.itinerary.start_date or self.date > self.itinerary.end_date:
                raise ValidationError({'date': "Day's date must fall within the itinerary's date range."})
