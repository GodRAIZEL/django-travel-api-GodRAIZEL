"""Accommodation, Activity and Booking models."""
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


def validate_image_size(image):
    max_mb = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 5)
    if image.size > max_mb * 1024 * 1024:
        raise ValidationError(f'Image file too large. Max size is {max_mb}MB.')


def validate_image_extension(image):
    ext = os.path.splitext(image.name)[1].lower()
    allowed = ['.jpg', '.jpeg', '.png', '.webp']
    if ext not in allowed:
        raise ValidationError(f'Unsupported file type "{ext}". Allowed: {", ".join(allowed)}')


class Accommodation(models.Model):
    """Hotels, hostels, vacation rentals available at a destination."""

    class TypeChoices(models.TextChoices):
        HOTEL = 'hotel', 'Hotel'
        HOSTEL = 'hostel', 'Hostel'
        RENTAL = 'rental', 'Vacation Rental'
        RESORT = 'resort', 'Resort'
        BNB = 'bnb', 'B&B'

    name = models.CharField(max_length=200)
    destination = models.ForeignKey(
        'destinations.Destination', on_delete=models.CASCADE, related_name='accommodations'
    )
    accommodation_type = models.CharField(max_length=10, choices=TypeChoices.choices)
    description = models.TextField()
    price_per_night = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    max_guests = models.PositiveIntegerField(default=1)
    amenities = models.JSONField(default=list, blank=True)
    address = models.CharField(max_length=300, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    image = models.ImageField(
        upload_to='accommodations/', null=True, blank=True,
        validators=[validate_image_size, validate_image_extension],
    )
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['destination', 'accommodation_type']),
            models.Index(fields=['is_available']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_accommodation_type_display()})"

    def clean(self):
        if self.price_per_night is not None and self.price_per_night < 0:
            raise ValidationError({'price_per_night': 'Price cannot be negative.'})

    def nightly_total(self, nights):
        """Business-logic helper: total accommodation cost for N nights."""
        return self.price_per_night * max(nights, 0)


class Activity(models.Model):
    """Tours, attractions and experiences available at a destination."""

    class CategoryChoices(models.TextChoices):
        TOUR = 'tour', 'Tour'
        ATTRACTION = 'attraction', 'Attraction'
        DINING = 'dining', 'Dining'
        SHOPPING = 'shopping', 'Shopping'
        ENTERTAINMENT = 'entertainment', 'Entertainment'
        OUTDOOR = 'outdoor', 'Outdoor'

    name = models.CharField(max_length=200)
    destination = models.ForeignKey(
        'destinations.Destination', on_delete=models.CASCADE, related_name='activities'
    )
    category = models.CharField(max_length=20, choices=CategoryChoices.choices)
    description = models.TextField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    requirements = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='activities/', null=True, blank=True,
        validators=[validate_image_size, validate_image_extension],
    )
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Activities'
        indexes = [
            models.Index(fields=['destination', 'category']),
        ]

    def __str__(self):
        return f"{self.name} - {self.destination.name}"

    def clean(self):
        if self.price is not None and self.price < 0:
            raise ValidationError({'price': 'Price cannot be negative.'})


class Booking(models.Model):
    """A user's booking of either an accommodation stay or an activity slot."""

    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings'
    )
    itinerary = models.ForeignKey(
        'itineraries.Itinerary', on_delete=models.CASCADE, related_name='bookings'
    )
    accommodation = models.ForeignKey(
        Accommodation, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )
    activity = models.ForeignKey(
        Activity, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )
    booking_date = models.DateField()
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    guests_count = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    confirmation_code = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['itinerary']),
        ]

    def __str__(self):
        if self.accommodation:
            return f"Booking: {self.accommodation.name}"
        if self.activity:
            return f"Booking: {self.activity.name}"
        return f"Booking #{self.id}"

    def clean(self):
        if not self.accommodation and not self.activity:
            raise ValidationError('Booking must reference either an accommodation or an activity.')
        if self.accommodation and self.activity:
            raise ValidationError('Booking cannot reference both an accommodation and an activity.')
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValidationError({'check_out': 'Check-out date must be after check-in date.'})

    def confirm(self):
        """Business-logic helper: transition a pending booking to confirmed."""
        if self.status != self.StatusChoices.PENDING:
            raise ValidationError('Only pending bookings can be confirmed.')
        self.status = self.StatusChoices.CONFIRMED
        self.confirmation_code = uuid.uuid4().hex[:10].upper()
        self.save(update_fields=['status', 'confirmation_code', 'updated_at'])
        return self

    def cancel(self):
        """Business-logic helper: cancel a booking and compute a simple refund estimate."""
        if self.status == self.StatusChoices.CANCELLED:
            raise ValidationError('Booking is already cancelled.')
        refund_pct = 1.0 if self.status == self.StatusChoices.PENDING else 0.5
        refund_amount = round(float(self.price) * refund_pct, 2)
        self.status = self.StatusChoices.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
        return refund_amount
