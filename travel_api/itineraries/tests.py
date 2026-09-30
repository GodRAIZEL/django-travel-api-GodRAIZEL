"""Tests for itineraries, collaboration and daily plans."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from destinations.models import Destination

from .models import Itinerary

User = get_user_model()


def _make_destination(name='Paris'):
    return Destination.objects.create(
        name=name, country='France', description='City of lights',
        category=Destination.CategoryChoices.CITY,
        climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=150,
    )


class ItineraryModelTests(APITestCase):
    """Test Itinerary model validation and helper methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='modeltester', email='modeltester@example.com', password='TestPass123')
        self.destination = _make_destination()

    def test_duration_days_property(self):
        itinerary = Itinerary.objects.create(
            title='Trip', destination=self.destination, owner=self.user,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 7), budget=1000,
        )
        self.assertEqual(itinerary.duration_days, 7)

    def test_end_date_before_start_date_invalid(self):
        itinerary = Itinerary(
            title='Bad Trip', destination=self.destination, owner=self.user,
            start_date=date(2026, 6, 10), end_date=date(2026, 6, 1), budget=1000,
        )
        with self.assertRaises(Exception):
            itinerary.full_clean()

    def test_add_collaborator(self):
        collaborator = User.objects.create_user(username='collab1', email='collab1@example.com', password='TestPass123')
        itinerary = Itinerary.objects.create(
            title='Shared Trip', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=3), budget=500,
        )
        itinerary.add_collaborator(collaborator, role='editor')
        self.assertEqual(itinerary.role_for(collaborator), 'editor')
        self.assertEqual(itinerary.role_for(self.user), 'owner')


class ItineraryAPITestCase(APITestCase):
    """Test itinerary CRUD operations via the ViewSet."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client = self.client_class()
        self.client.force_authenticate(user=self.user)
        self.destination = _make_destination()
        self.itinerary = Itinerary.objects.create(
            title='Paris Trip', destination=self.destination, owner=self.user,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 7), budget=2000,
        )

    def test_list_itineraries(self):
        """Test retrieving list of user's itineraries."""
        response = self.client.get('/api/v1/itineraries/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_itinerary(self):
        """Test creating new itinerary."""
        data = {
            'title': 'Rome Adventure',
            'destination': self.destination.id,
            'start_date': '2026-07-01',
            'end_date': '2026-07-10',
            'budget': 3000,
        }
        response = self.client.post('/api/v1/itineraries/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Itinerary.objects.count(), 2)

    def test_update_itinerary(self):
        """Test updating existing itinerary."""
        data = {'budget': 2500}
        response = self.client.patch(f'/api/v1/itineraries/{self.itinerary.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.itinerary.refresh_from_db()
        self.assertEqual(float(self.itinerary.budget), 2500)

    def test_delete_itinerary(self):
        """Test deleting itinerary."""
        response = self.client.delete(f'/api/v1/itineraries/{self.itinerary.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Itinerary.objects.count(), 0)

    def test_unauthorized_access(self):
        """Test that unauthenticated users cannot access."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/itineraries/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_update_others_itinerary(self):
        """Test users cannot update others' itineraries."""
        other_user = User.objects.create_user(username='other', email='other@example.com', password='pass12345')
        self.client.force_authenticate(user=other_user)
        response = self.client.patch(f'/api/v1/itineraries/{self.itinerary.id}/', {'budget': 5000})
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_duplicate_action(self):
        response = self.client.post(f'/api/v1/itineraries/{self.itinerary.id}/duplicate/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Itinerary.objects.count(), 2)

    def test_upcoming_trips_action(self):
        response = self.client.get('/api/v1/itineraries/upcoming/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CollaborationPermissionTests(APITestCase):
    """Test custom object-level permissions for collaboration roles."""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', password='pass12345')
        self.collaborator = User.objects.create_user(username='collab', email='collab@example.com', password='pass12345')
        self.viewer = User.objects.create_user(username='viewer', email='viewer@example.com', password='pass12345')
        self.destination = _make_destination('Tokyo')
        self.itinerary = Itinerary.objects.create(
            title='Test Trip', destination=self.destination, owner=self.owner,
            start_date=date.today(), end_date=date.today() + timedelta(days=3), budget=1000,
        )

    def test_owner_can_edit(self):
        """Test owner has full permissions."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(f'/api/v1/itineraries/{self.itinerary.id}/', {'title': 'Updated'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_editor_collaborator_can_edit(self):
        """Test collaborator permissions based on role."""
        self.itinerary.add_collaborator(self.collaborator, role='editor')
        self.client.force_authenticate(user=self.collaborator)
        response = self.client.patch(
            f'/api/v1/itineraries/{self.itinerary.id}/', {'title': 'Updated by Collab'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_viewer_collaborator_cannot_edit(self):
        self.itinerary.add_collaborator(self.viewer, role='viewer')
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(
            f'/api/v1/itineraries/{self.itinerary.id}/', {'title': 'Should not work'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_share_with_user_action(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f'/api/v1/itineraries/{self.itinerary.id}/share/',
            {'email': self.collaborator.email, 'role': 'viewer'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_share_with_unknown_email_fails(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f'/api/v1/itineraries/{self.itinerary.id}/share/',
            {'email': 'nobody@example.com', 'role': 'viewer'},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_pdf_action(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/v1/itineraries/{self.itinerary.id}/export_pdf/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.itinerary.title, response.content.decode())

    def test_viewer_collaborator_can_read(self):
        self.itinerary.add_collaborator(self.viewer, role='viewer')
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get(f'/api/v1/itineraries/{self.itinerary.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unrelated_user_cannot_read(self):
        outsider = User.objects.create_user(username='outsider', email='outsider@example.com', password='pass12345')
        self.client.force_authenticate(user=outsider)
        response = self.client.get(f'/api/v1/itineraries/{self.itinerary.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_owner_cannot_delete(self):
        self.itinerary.add_collaborator(self.collaborator, role='admin')
        self.client.force_authenticate(user=self.collaborator)
        response = self.client.delete(f'/api/v1/itineraries/{self.itinerary.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'/api/v1/itineraries/{self.itinerary.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TripSearchAndReportTests(APITestCase):
    """Test the trip_search and generate_trip_report FBVs."""

    def setUp(self):
        self.user = User.objects.create_user(username='searcher', email='searcher@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = _make_destination('Prague')
        self.itinerary = Itinerary.objects.create(
            title='Prague Weekend', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=3), budget=800,
            actual_spent=200,
        )

    def test_trip_search_get(self):
        response = self.client.get(reverse('itineraries:trip-search'), {'q': 'Prague'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_trip_search_post_saves_preferences(self):
        response = self.client.post(reverse('itineraries:trip-search'), {'status': 'planning'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.user.refresh_from_db()
        self.assertIn('itinerary_search', self.user.travel_preferences)

    def test_generate_trip_report(self):
        response = self.client.get(reverse('itineraries:trip-report', args=[self.itinerary.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bookings']['count'], 0)
        self.assertIn('expenses_by_category', response.data)

    def test_generate_trip_report_404_for_unrelated_trip(self):
        other_user = User.objects.create_user(username='notinvolved', email='notinvolved@example.com', password='TestPass123')
        other_itinerary = Itinerary.objects.create(
            title='Someone Else\'s Trip', destination=self.destination, owner=other_user,
            start_date=date.today(), end_date=date.today() + timedelta(days=2), budget=300,
        )
        response = self.client.get(reverse('itineraries:trip-report', args=[other_itinerary.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ItineraryListCreateViewTests(APITestCase):
    """Test the ItineraryListCreateView CBV."""

    def setUp(self):
        self.user = User.objects.create_user(username='listcreateuser', email='listcreate@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = _make_destination('Dublin')

    def test_list_own_itineraries(self):
        Itinerary.objects.create(
            title='Dublin Trip', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=2), budget=400,
        )
        response = self.client.get(reverse('itineraries:itinerary-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_create_via_cbv(self):
        data = {
            'title': 'Dublin Adventure', 'destination_id': self.destination.id,
            'start_date': str(date.today()), 'end_date': str(date.today() + timedelta(days=4)),
            'budget': 600,
        }
        response = self.client.post(reverse('itineraries:itinerary-create'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TripCollaborationViewTests(APITestCase):
    """Test the TripCollaborationView CBV: add, update role, remove."""

    def setUp(self):
        self.owner = User.objects.create_user(username='collabowner', email='collabowner@example.com', password='TestPass123')
        self.invitee = User.objects.create_user(username='invitee', email='invitee@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.owner)
        self.destination = _make_destination('Seville')
        self.itinerary = Itinerary.objects.create(
            title='Seville Trip', destination=self.destination, owner=self.owner,
            start_date=date.today(), end_date=date.today() + timedelta(days=3), budget=500,
        )
        self.add_url = reverse('itineraries:collaborators-add', args=[self.itinerary.id])

    def test_add_collaborator(self):
        response = self.client.post(self.add_url, {'user_id': self.invitee.id, 'role': 'editor'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_add_owner_as_collaborator(self):
        response = self.client.post(self.add_url, {'user_id': self.owner.id, 'role': 'viewer'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_add_same_collaborator_twice(self):
        self.client.post(self.add_url, {'user_id': self.invitee.id, 'role': 'viewer'})
        response = self.client.post(self.add_url, {'user_id': self.invitee.id, 'role': 'editor'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_and_remove_collaborator(self):
        self.client.post(self.add_url, {'user_id': self.invitee.id, 'role': 'viewer'})
        manage_url = reverse('itineraries:collaborators-manage', args=[self.itinerary.id, self.invitee.id])
        patch_response = self.client.patch(manage_url, {'role': 'admin'})
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['role'], 'admin')
        delete_response = self.client.delete(manage_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_non_owner_non_admin_cannot_manage_collaborators(self):
        self.client.force_authenticate(user=self.invitee)
        response = self.client.post(self.add_url, {'user_id': self.invitee.id, 'role': 'viewer'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_collaborator_can_manage_collaborators(self):
        self.itinerary.add_collaborator(self.invitee, role='admin')
        third_user = User.objects.create_user(username='thirdperson', email='third@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.invitee)
        response = self.client.post(self.add_url, {'user_id': third_user.id, 'role': 'viewer'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TripAnalyticsViewSetTests(APITestCase):
    """Test the read-only analytics endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(username='analyst', email='analyst@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = _make_destination('Nairobi')
        self.itinerary = Itinerary.objects.create(
            title='Kenya Safari', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=8), budget=2500,
            actual_spent=600,
        )

    def test_analytics_list(self):
        response = self.client.get('/api/v1/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_trips'], 1)

    def test_budget_summary(self):
        response = self.client.get('/api/v1/analytics/budget_summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('by_category', response.data)

    def test_destination_preferences(self):
        response = self.client.get('/api/v1/analytics/destination_preferences/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('by_category', response.data)
        self.assertIn('by_climate', response.data)
