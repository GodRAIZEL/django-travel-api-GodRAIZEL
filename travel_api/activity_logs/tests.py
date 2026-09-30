"""Tests for the activity/audit log."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from destinations.models import Destination
from itineraries.models import Itinerary

from .models import ActivityLog

User = get_user_model()


class ActivityLogModelTests(APITestCase):
    """Test the ActivityLog.record() helper."""

    def setUp(self):
        self.user = User.objects.create_user(username='loguser', email='loguser@example.com', password='TestPass123')

    def test_record_creates_entry(self):
        entry = ActivityLog.record(
            user=self.user, action=ActivityLog.ActionChoices.ITINERARY_CREATED,
            description='Created a test itinerary', foo='bar',
        )
        self.assertEqual(entry.action, ActivityLog.ActionChoices.ITINERARY_CREATED)
        self.assertEqual(entry.metadata, {'foo': 'bar'})


class ActivityLogIntegrationTests(APITestCase):
    """Test that key actions elsewhere in the API actually write log entries."""

    def setUp(self):
        self.user = User.objects.create_user(username='actor', email='actor@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = Destination.objects.create(
            name='Vienna', country='Austria', description='Imperial city',
            category=Destination.CategoryChoices.CULTURAL,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=130,
        )

    def test_creating_itinerary_logs_entry(self):
        data = {
            'title': 'Vienna Trip', 'destination': self.destination.id,
            'start_date': str(date.today()), 'end_date': str(date.today() + timedelta(days=5)),
            'budget': 1200,
        }
        response = self.client.post('/api/v1/itineraries/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ActivityLog.objects.filter(
                user=self.user, action=ActivityLog.ActionChoices.ITINERARY_CREATED
            ).exists()
        )

    def test_deleting_itinerary_logs_entry(self):
        itinerary = Itinerary.objects.create(
            title='To Delete', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=3), budget=500,
        )
        response = self.client.delete(f'/api/v1/itineraries/{itinerary.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(
            ActivityLog.objects.filter(action=ActivityLog.ActionChoices.ITINERARY_DELETED).exists()
        )

    def test_activity_log_list_scoped_to_user(self):
        other = User.objects.create_user(username='otheractor', email='otheractor@example.com', password='TestPass123')
        ActivityLog.record(user=other, action=ActivityLog.ActionChoices.BOOKING_CREATED, description='Not mine')
        ActivityLog.record(user=self.user, action=ActivityLog.ActionChoices.BOOKING_CREATED, description='Mine')
        response = self.client.get('/api/v1/activity-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        descriptions = [row['description'] for row in response.data['results']]
        self.assertIn('Mine', descriptions)
        self.assertNotIn('Not mine', descriptions)
