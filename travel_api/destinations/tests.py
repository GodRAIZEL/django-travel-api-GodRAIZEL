"""Tests for destination models and endpoints."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Destination

User = get_user_model()


class DestinationModelTests(APITestCase):
    """Test Destination model behaviour."""

    def test_str_representation(self):
        destination = Destination.objects.create(
            name='Cape Town', country='South Africa', description='Coastal city',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE,
            avg_daily_cost=80,
        )
        self.assertEqual(str(destination), 'Cape Town, South Africa')

    def test_budget_tier_classification(self):
        cheap = Destination.objects.create(
            name='Budget Town', country='Testland', description='x',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=50,
        )
        luxury = Destination.objects.create(
            name='Luxury Town', country='Testland', description='x',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=500,
        )
        self.assertEqual(cheap.budget_tier(), 'budget')
        self.assertEqual(luxury.budget_tier(), 'luxury')

    def test_average_rating_with_no_reviews(self):
        destination = Destination.objects.create(
            name='Quiet Town', country='Testland', description='x',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=100,
        )
        self.assertEqual(destination.average_rating, 0.0)


class DestinationAPITests(APITestCase):
    """Test the destination browsing endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(username='browser', email='browser@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = Destination.objects.create(
            name='Paris', country='France', description='City of lights',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=150,
        )

    def test_list_destinations(self):
        response = self.client.get('/api/v1/destinations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_retrieve_destination(self):
        response = self.client.get(f'/api/v1/destinations/{self.destination.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Paris')

    def test_filter_by_category(self):
        response = self.client.get('/api/v1/destinations/?category=city')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_search_view(self):
        response = self.client.get(reverse('destinations:destination-search'), {'q': 'Paris'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_weather_info_action(self):
        response = self.client.get(f'/api/v1/destinations/{self.destination.id}/weather_info/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('avg_temp_c', response.data)

    def test_search_view_saves_preferences(self):
        response = self.client.post(
            reverse('destinations:destination-search'), {'q': 'Paris', 'min_cost': 50}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertIn('saved_search', self.user.travel_preferences)

    def test_recommendations_endpoint(self):
        response = self.client.get(reverse('destinations:destination-recommendations'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_recommendations_matches_stated_category_preference(self):
        self.user.travel_preferences = {'categories': ['city']}
        self.user.save(update_fields=['travel_preferences'])
        response = self.client.get(reverse('destinations:destination-recommendations'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['matched_on_preferences'])

    def test_popular_activities_action(self):
        response = self.client.get(f'/api/v1/destinations/{self.destination.id}/popular_activities/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reviews_summary_action(self):
        response = self.client.get(f'/api/v1/destinations/{self.destination.id}/reviews_summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('average_rating', response.data)
        self.assertIn('breakdown', response.data)
