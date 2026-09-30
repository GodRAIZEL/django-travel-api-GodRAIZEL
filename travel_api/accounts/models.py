"""
Custom user model and related account models.
"""
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


def validate_profile_picture_size(image):
    """Reject profile pictures larger than settings.MAX_UPLOAD_SIZE_MB."""
    from django.conf import settings
    max_mb = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 5)
    if image.size > max_mb * 1024 * 1024:
        raise ValidationError(f'Image file too large. Max size is {max_mb}MB.')


class User(AbstractUser):
    """
    Custom user model extending AbstractUser with travel-app-specific
    profile fields. Email is required and unique so it can double as a
    login/recovery identifier.
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(
        upload_to='profiles/',
        null=True,
        blank=True,
        validators=[validate_profile_picture_size],
    )
    travel_preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.username

    def clean(self):
        super().clean()
        if self.date_of_birth:
            from datetime import date
            if self.date_of_birth > date.today():
                raise ValidationError({'date_of_birth': 'Date of birth cannot be in the future.'})

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def preferred_categories(self):
        """Business-logic helper: pull the 'categories' list a user set in
        travel_preferences, used by the recommendation endpoints."""
        return self.travel_preferences.get('categories', [])
