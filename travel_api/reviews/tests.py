"""Tests for the Review model and API."""
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from destinations.models import Destination

from .models import Review

User = get_user_model()


class ReviewModelTests(APITestCase):
    """Test Review model validation."""

    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', email='reviewer@example.com', password='TestPass123')
        self.destination = Destination.objects.create(
            name='Lisbon', country='Portugal', description='Coastal capital',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=90,
        )

    def test_review_requires_exactly_one_target(self):
        review = Review(
            user=self.user, rating=5, title='Great', content='Loved it', visit_date=date.today(),
        )
        with self.assertRaises(Exception):
            review.full_clean()

    def test_valid_review_passes_clean(self):
        review = Review(
            user=self.user, destination=self.destination, rating=5, title='Great',
            content='Loved it', visit_date=date.today(),
        )
        review.full_clean()  # should not raise

    def test_mark_helpful_increments_counter(self):
        review = Review.objects.create(
            user=self.user, destination=self.destination, rating=4, title='Nice',
            content='Would come again', visit_date=date.today(),
        )
        new_count = review.mark_helpful()
        self.assertEqual(new_count, 1)


class ReviewAPITests(APITestCase):
    """Test the Review ViewSet."""

    def setUp(self):
        self.user = User.objects.create_user(username='reviewapi', email='reviewapi@example.com', password='TestPass123')
        self.other_user = User.objects.create_user(username='otherreviewer', email='otherreviewer@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = Destination.objects.create(
            name='Berlin', country='Germany', description='Capital city',
            category=Destination.CategoryChoices.CITY,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=100,
        )

    def test_create_review(self):
        data = {
            'destination': self.destination.id, 'rating': 5, 'title': 'Amazing',
            'content': 'Best trip ever', 'visit_date': str(date.today()),
        }
        response = self.client.post('/api/v1/reviews/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_review_with_two_targets_fails(self):
        data = {
            'destination': self.destination.id, 'accommodation': 1, 'rating': 5,
            'title': 'Amazing', 'content': 'Best trip ever', 'visit_date': str(date.today()),
        }
        response = self.client.post('/api/v1/reviews/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_edit_others_review(self):
        review = Review.objects.create(
            user=self.other_user, destination=self.destination, rating=3, title='OK',
            content='It was fine', visit_date=date.today(),
        )
        response = self.client.patch(f'/api/v1/reviews/{review.id}/', {'title': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mark_helpful_action(self):
        review = Review.objects.create(
            user=self.other_user, destination=self.destination, rating=4, title='Good',
            content='Solid trip', visit_date=date.today(),
        )
        response = self.client.post(f'/api/v1/reviews/{review.id}/mark_helpful/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['helpful_count'], 1)

    def test_my_reviews_action(self):
        Review.objects.create(
            user=self.user, destination=self.destination, rating=5, title='Mine',
            content='By me', visit_date=date.today(),
        )
        Review.objects.create(
            user=self.other_user, destination=self.destination, rating=3, title='Not mine',
            content='By someone else', visit_date=date.today(),
        )
        response = self.client.get('/api/v1/reviews/my_reviews/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [r['title'] for r in response.data]
        self.assertIn('Mine', titles)
        self.assertNotIn('Not mine', titles)

    def test_list_and_retrieve_reviews(self):
        review = Review.objects.create(
            user=self.other_user, destination=self.destination, rating=4, title='Nice place',
            content='Would visit again', visit_date=date.today(),
        )
        list_response = self.client.get('/api/v1/reviews/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        detail_response = self.client.get(f'/api/v1/reviews/{review.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['subject_type'], 'destination')

    def test_visit_date_in_future_rejected(self):
        from datetime import timedelta
        future = date.today() + timedelta(days=5)
        response = self.client.post('/api/v1/reviews/', {
            'destination': self.destination.id, 'rating': 5, 'title': 'Too soon',
            'content': 'Have not gone yet', 'visit_date': str(future),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
