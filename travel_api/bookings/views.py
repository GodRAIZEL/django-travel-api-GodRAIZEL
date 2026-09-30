"""
Views for accommodations, activities and bookings.

Includes a function-based view (bulk booking updates - atomic, custom
business logic), a class-based generic view (booking detail management)
and three ViewSets (accommodations, activities, bookings).
"""
from datetime import date

from django.db import transaction
from django.db.models import Avg, Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from activity_logs.models import ActivityLog
from .filters import BookingFilter
from .models import Accommodation, Activity, Booking
from .permissions import IsBookingOwner, IsStaffOrReadOnly
from .serializers import (
    AccommodationSerializer,
    ActivitySerializer,
    BookingDetailSerializer,
    BookingListSerializer,
)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_update_bookings(request):
    """
    POST: Update multiple bookings (e.g. status changes) in a single atomic
    request. Body shape: {"updates": [{"id": 1, "status": "confirmed"}, ...]}.
    Returns per-item success/failure so a client can retry just the failures.
    """
    updates = request.data.get('updates', [])
    if not isinstance(updates, list) or not updates:
        return Response({'detail': "'updates' must be a non-empty list."}, status=status.HTTP_400_BAD_REQUEST)

    results = {'succeeded': [], 'failed': []}
    allowed_statuses = {choice.value for choice in Booking.StatusChoices}

    with transaction.atomic():
        for item in updates:
            booking_id = item.get('id')
            new_status = item.get('status')
            try:
                booking = Booking.objects.get(id=booking_id, user=request.user)
                if new_status not in allowed_statuses:
                    raise ValueError(f'Invalid status "{new_status}".')
                booking.status = new_status
                booking.full_clean()
                booking.save(update_fields=['status', 'updated_at'])
                results['succeeded'].append(booking_id)
            except (Booking.DoesNotExist, ValueError, Exception) as exc:  # noqa: BLE001
                results['failed'].append({'id': booking_id, 'error': str(exc)})

    response_status = status.HTTP_200_OK if not results['failed'] else status.HTTP_207_MULTI_STATUS \
        if hasattr(status, 'HTTP_207_MULTI_STATUS') else status.HTTP_200_OK
    return Response(results, status=response_status)


class BookingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or cancel (delete) a specific booking owned by the requester."""
    serializer_class = BookingDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookingOwner]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            'accommodation', 'activity', 'itinerary'
        )


class AccommodationViewSet(viewsets.ModelViewSet):
    """Browse (everyone authenticated) and manage (staff only) accommodations."""
    serializer_class = AccommodationSerializer
    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['destination', 'accommodation_type', 'is_available']
    search_fields = ['name', 'description', 'address']
    ordering_fields = ['price_per_night', 'name', 'created_at']

    def get_queryset(self):
        return Accommodation.objects.select_related('destination').prefetch_related('reviews').annotate(
            rating=Avg('reviews__rating')
        )


class ActivityViewSet(viewsets.ModelViewSet):
    """Browse (everyone authenticated) and manage (staff only) activities."""
    serializer_class = ActivitySerializer
    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['destination', 'category', 'is_available']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'name', 'created_at']

    def get_queryset(self):
        # only() - keep the columns tight for the common list/retrieve path;
        # every field the serializer actually renders is included here so
        # accessing them doesn't trigger a second per-row query.
        return Activity.objects.select_related('destination').only(
            'id', 'name', 'category', 'description', 'duration_hours', 'price',
            'max_participants', 'requirements', 'is_available', 'image', 'created_at',
            'destination__id', 'destination__name',
        ).prefetch_related('reviews').annotate(
            booking_count=Count('bookings')
        )


class BookingViewSet(viewsets.ModelViewSet):
    """Full CRUD for the requesting user's own bookings, plus confirm/cancel actions."""
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BookingFilter
    search_fields = ['notes', 'confirmation_code']
    ordering_fields = ['created_at', 'booking_date', 'price']

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            'accommodation', 'activity', 'itinerary'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return BookingListSerializer
        return BookingDetailSerializer

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy', 'confirm', 'cancel']:
            return [permissions.IsAuthenticated(), IsBookingOwner()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        booking_date = serializer.validated_data.get('booking_date') or date.today()
        booking = serializer.save(user=self.request.user, booking_date=booking_date)
        ActivityLog.record(
            user=self.request.user, action=ActivityLog.ActionChoices.BOOKING_CREATED,
            description=f'Created booking #{booking.id} on itinerary "{booking.itinerary.title}"',
            itinerary=booking.itinerary,
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """POST: Confirm a pending booking and issue a confirmation code."""
        booking = self.get_object()
        try:
            booking.confirm()
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        ActivityLog.record(
            user=request.user, action=ActivityLog.ActionChoices.BOOKING_CONFIRMED,
            description=f'Confirmed booking #{booking.id}', itinerary=booking.itinerary,
        )
        return Response(BookingDetailSerializer(booking, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST: Cancel a booking and return the estimated refund amount."""
        booking = self.get_object()
        try:
            refund_amount = booking.cancel()
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        ActivityLog.record(
            user=request.user, action=ActivityLog.ActionChoices.BOOKING_CANCELLED,
            description=f'Cancelled booking #{booking.id}', itinerary=booking.itinerary,
            refund_amount=refund_amount,
        )
        return Response({
            'detail': 'Booking cancelled.',
            'refund_amount': refund_amount,
            'booking': BookingDetailSerializer(booking, context={'request': request}).data,
        })
