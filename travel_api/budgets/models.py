"""Budget tracking models: per-trip category budgets and individual expenses."""
import os

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


def validate_receipt_size(image):
    from django.conf import settings
    max_mb = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 5)
    if image.size > max_mb * 1024 * 1024:
        raise ValidationError(f'Receipt file too large. Max size is {max_mb}MB.')


def validate_receipt_extension(image):
    ext = os.path.splitext(image.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.pdf', '.webp']
    if ext not in allowed:
        raise ValidationError(f'Unsupported file type "{ext}". Allowed: {", ".join(allowed)}')


class Budget(models.Model):
    """Per-category budget allocation for a single itinerary (one-to-one)."""

    itinerary = models.OneToOneField(
        'itineraries.Itinerary', on_delete=models.CASCADE, related_name='budget_detail'
    )
    accommodation_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    activities_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    food_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    transport_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    shopping_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    miscellaneous_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Budget for {self.itinerary.title}"

    @property
    def total_budget(self):
        return (
            self.accommodation_budget + self.activities_budget + self.food_budget
            + self.transport_budget + self.shopping_budget + self.miscellaneous_budget
        )

    def spent_by_category(self):
        """Business-logic helper: actual spend per category, from linked Expense rows."""
        from django.db.models import Sum
        return dict(
            self.itinerary.expenses.values_list('category').annotate(total=Sum('amount'))
        )


class Expense(models.Model):
    """A single logged expense within a trip's budget."""

    class CategoryChoices(models.TextChoices):
        ACCOMMODATION = 'accommodation', 'Accommodation'
        ACTIVITIES = 'activities', 'Activities'
        FOOD = 'food', 'Food'
        TRANSPORT = 'transport', 'Transport'
        SHOPPING = 'shopping', 'Shopping'
        MISCELLANEOUS = 'miscellaneous', 'Miscellaneous'

    itinerary = models.ForeignKey(
        'itineraries.Itinerary', on_delete=models.CASCADE, related_name='expenses'
    )
    category = models.CharField(max_length=20, choices=CategoryChoices.choices)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    date = models.DateField()
    receipt = models.ImageField(
        upload_to='receipts/', null=True, blank=True,
        validators=[validate_receipt_size, validate_receipt_extension],
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['itinerary', 'category']),
        ]

    def __str__(self):
        return f"{self.description} - ${self.amount}"

    def clean(self):
        if self.amount is not None and self.amount < 0:
            raise ValidationError({'amount': 'Amount cannot be negative.'})
