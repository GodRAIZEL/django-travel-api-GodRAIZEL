"""Tests for accommodations, activities and bookings."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from destinations.models import Destination
from itineraries.models import Itinerary

from .models import Accommodation, Activity, Booking

User = get_user_model()


def _make_destination(name='Rome'):
    return Destination.objects.create(
        name=name, country='Italy', description='Ancient city',
        category=Destination.CategoryChoices.CULTURAL,
        climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=120,
    )


class BookingModelTests(APITestCase):
    """Test Booking model validation and business-logic methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='bookuser', email='bookuser@example.com', password='TestPass123')
        self.destination = _make_destination()
        self.itinerary = Itinerary.objects.create(
            title='Roman Holiday', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=5), budget=1000,
        )
        self.activity = Activity.objects.create(
            name='Colosseum Tour', destination=self.destination,
            category=Activity.CategoryChoices.TOUR, description='Guided tour',
            price=50,
        )

    def test_booking_requires_accommodation_or_activity(self):
        booking = Booking(
            user=self.user, itinerary=self.itinerary, booking_date=date.today(), price=0,
        )
        with self.assertRaises(Exception):
            booking.full_clean()

    def test_confirm_generates_confirmation_code(self):
        booking = Booking.objects.create(
            user=self.user, itinerary=self.itinerary, activity=self.activity,
            booking_date=date.today(), price=50,
        )
        booking.confirm()
        self.assertEqual(booking.status, Booking.StatusChoices.CONFIRMED)
        self.assertTrue(booking.confirmation_code)

    def test_cancel_returns_full_refund_when_pending(self):
        booking = Booking.objects.create(
            user=self.user, itinerary=self.itinerary, activity=self.activity,
            booking_date=date.today(), price=100,
        )
        refund = booking.cancel()
        self.assertEqual(refund, 100.0)
        self.assertEqual(booking.status, Booking.StatusChoices.CANCELLED)


class BookingAPITests(APITestCase):
    """Test the Booking ViewSet."""

    def setUp(self):
        self.user = User.objects.create_user(username='apibooker', email='apibooker@example.com', password='TestPass123')
        self.other_user = User.objects.create_user(username='otherbooker', email='otherbooker@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = _make_destination()
        self.itinerary = Itinerary.objects.create(
            title='Italy Trip', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=5), budget=1000,
        )
        self.activity = Activity.objects.create(
            name='Vatican Tour', destination=self.destination,
            category=Activity.CategoryChoices.TOUR, description='Guided tour', price=40,
        )
        self.booking = Booking.objects.create(
            user=self.user, itinerary=self.itinerary, activity=self.activity,
            booking_date=date.today(), price=40,
        )

    def test_list_bookings_only_returns_own(self):
        Booking.objects.create(
            user=self.other_user, itinerary=self.itinerary, activity=self.activity,
            booking_date=date.today(), price=40,
        )
        response = self.client.get('/api/v1/bookings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_create_booking(self):
        data = {
            'itinerary': self.itinerary.id,
            'activity': self.activity.id,
            'booking_date': str(date.today()),
            'guests_count': 2,
            'price': 40,
        }
        response = self.client.post('/api/v1/bookings/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_confirm_action(self):
        response = self.client.post(f'/api/v1/bookings/{self.booking.id}/confirm/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.StatusChoices.CONFIRMED)

    def test_cannot_confirm_others_booking(self):
        other_booking = Booking.objects.create(
            user=self.other_user, itinerary=self.itinerary, activity=self.activity,
            booking_date=date.today(), price=40,
        )
        response = self.client.post(f'/api/v1/bookings/{other_booking.id}/confirm/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_bulk_update_bookings(self):
        payload = {'updates': [{'id': self.booking.id, 'status': 'confirmed'}]}
        response = self.client.post('/api/v1/bookings/bulk-update/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.booking.id, response.data['succeeded'])

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/bookings/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_action(self):
        response = self.client.post(f'/api/v1/bookings/{self.booking.id}/cancel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['refund_amount'], 40.0)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.StatusChoices.CANCELLED)

    def test_cannot_confirm_an_already_cancelled_booking(self):
        self.booking.cancel()
        response = self.client.post(f'/api/v1/bookings/{self.booking.id}/confirm/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_update_bookings_rejects_invalid_status(self):
        payload = {'updates': [{'id': self.booking.id, 'status': 'not-a-real-status'}]}
        response = self.client.post('/api/v1/bookings/bulk-update/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(len(response.data['failed']), 1)

    def test_bulk_update_bookings_requires_updates_list(self):
        response = self.client.post('/api/v1/bookings/bulk-update/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_detail_cbv_get_and_delete(self):
        response = self.client.get(f'/api/v1/bookings/{self.booking.id}/manage/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.delete(f'/api/v1/bookings/{self.booking.id}/manage/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_booking_detail_cbv_forbidden_for_other_user(self):
        other_booking = Booking.objects.create(
            user=self.other_user, itinerary=self.itinerary, activity=self.activity,
            booking_date=date.today(), price=40,
        )
        response = self.client.get(f'/api/v1/bookings/{other_booking.id}/manage/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AccommodationActivityAPITests(APITestCase):
    """Test the read (everyone) / write (staff-only) split on Accommodation and Activity."""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staffer', email='staffer@example.com', password='TestPass123', is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regularjoe', email='regularjoe@example.com', password='TestPass123',
        )
        self.destination = _make_destination('Athens')
        self.accommodation = Accommodation.objects.create(
            name='Acropolis Hotel', destination=self.destination,
            accommodation_type=Accommodation.TypeChoices.HOTEL, description='Central',
            price_per_night=120,
        )

    def test_regular_user_can_list_accommodations(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/accommodations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_cannot_create_accommodation(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post('/api/v1/accommodations/', {
            'name': 'New Place', 'destination': self.destination.id,
            'accommodation_type': 'hotel', 'description': 'x', 'price_per_night': 90,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_create_activity(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post('/api/v1/activities/', {
            'name': 'Parthenon Tour', 'destination': self.destination.id,
            'category': 'tour', 'description': 'Guided walk', 'duration_hours': 2, 'price': 25,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_staff_user_can_update_accommodation(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.patch(
            f'/api/v1/accommodations/{self.accommodation.id}/', {'price_per_night': 150}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
