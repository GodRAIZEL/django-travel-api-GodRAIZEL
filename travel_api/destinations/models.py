"""Destination browsing models."""
from django.core.validators import MinValueValidator
from django.db import models


class Destination(models.Model):
    """A place travelers can build itineraries around (city, region, resort area)."""

    class ClimateChoices(models.TextChoices):
        TROPICAL = 'tropical', 'Tropical'
        DRY = 'dry', 'Dry'
        TEMPERATE = 'temperate', 'Temperate'
        CONTINENTAL = 'continental', 'Continental'
        POLAR = 'polar', 'Polar'

    class CategoryChoices(models.TextChoices):
        BEACH = 'beach', 'Beach'
        MOUNTAIN = 'mountain', 'Mountain'
        CITY = 'city', 'City'
        CULTURAL = 'cultural', 'Cultural'
        ADVENTURE = 'adventure', 'Adventure'
        RELAXATION = 'relaxation', 'Relaxation'

    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CategoryChoices.choices)
    climate = models.CharField(max_length=20, choices=ClimateChoices.choices)
    best_time_to_visit = models.CharField(max_length=200, blank=True)
    avg_daily_cost = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    image = models.ImageField(upload_to='destinations/', null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Destinations'
        indexes = [
            models.Index(fields=['country', 'category']),
            models.Index(fields=['climate']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name}, {self.country}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.avg_daily_cost is not None and self.avg_daily_cost < 0:
            raise ValidationError({'avg_daily_cost': 'Average daily cost cannot be negative.'})

    @property
    def average_rating(self):
        """Business-logic helper used by serializers: mean of all linked reviews."""
        result = self.reviews.aggregate(models.Avg('rating'))
        return round(result['rating__avg'], 2) if result['rating__avg'] else 0.0

    def budget_tier(self):
        """Classify the destination into a budget tier used by filters/recommendations."""
        if self.avg_daily_cost < 100:
            return 'budget'
        if self.avg_daily_cost < 250:
            return 'moderate'
        return 'luxury'
