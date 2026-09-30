"""Tests for Budget and Expense models and endpoints."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from destinations.models import Destination
from itineraries.models import Itinerary

from .models import Budget, Expense

User = get_user_model()


class BudgetModelTests(APITestCase):
    """Test Budget model's computed properties."""

    def setUp(self):
        self.user = User.objects.create_user(username='budgetuser', email='budgetuser@example.com', password='TestPass123')
        self.destination = Destination.objects.create(
            name='Kyoto', country='Japan', description='Historic city',
            category=Destination.CategoryChoices.CULTURAL,
            climate=Destination.ClimateChoices.TEMPERATE, avg_daily_cost=110,
        )
        self.itinerary = Itinerary.objects.create(
            title='Japan Trip', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=10), budget=3000,
        )

    def test_total_budget_sums_categories(self):
        budget = Budget.objects.create(
            itinerary=self.itinerary, accommodation_budget=1000, activities_budget=500,
            food_budget=300, transport_budget=200, shopping_budget=100, miscellaneous_budget=50,
        )
        self.assertEqual(budget.total_budget, 2150)

    def test_spent_by_category(self):
        budget = Budget.objects.create(itinerary=self.itinerary, food_budget=500)
        Expense.objects.create(
            itinerary=self.itinerary, category=Expense.CategoryChoices.FOOD,
            description='Dinner', amount=50, date=date.today(),
        )
        Expense.objects.create(
            itinerary=self.itinerary, category=Expense.CategoryChoices.FOOD,
            description='Lunch', amount=25, date=date.today(),
        )
        spent = budget.spent_by_category()
        self.assertEqual(spent.get('food'), 75)


class ExpenseAPITests(APITestCase):
    """Test expense creation keeps the parent itinerary's actual_spent in sync."""

    def setUp(self):
        self.user = User.objects.create_user(username='expenseuser', email='expenseuser@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = Destination.objects.create(
            name='Bali', country='Indonesia', description='Island paradise',
            category=Destination.CategoryChoices.BEACH,
            climate=Destination.ClimateChoices.TROPICAL, avg_daily_cost=70,
        )
        self.itinerary = Itinerary.objects.create(
            title='Bali Getaway', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=7), budget=1500,
        )

    def test_create_expense_updates_actual_spent(self):
        data = {
            'itinerary': self.itinerary.id, 'category': 'food',
            'description': 'Beach dinner', 'amount': 45, 'date': str(date.today()),
        }
        response = self.client.post('/api/v1/expenses/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.itinerary.refresh_from_db()
        self.assertEqual(float(self.itinerary.actual_spent), 45.0)

    def test_delete_expense_reduces_actual_spent(self):
        expense = Expense.objects.create(
            itinerary=self.itinerary, category=Expense.CategoryChoices.FOOD,
            description='Snacks', amount=20, date=date.today(),
        )
        self.itinerary.actual_spent = 20
        self.itinerary.save(update_fields=['actual_spent'])
        response = self.client.delete(f'/api/v1/expenses/{expense.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.itinerary.refresh_from_db()
        self.assertEqual(float(self.itinerary.actual_spent), 0.0)

    def test_other_user_cannot_access_expenses(self):
        other = User.objects.create_user(username='notowner', email='notowner@example.com', password='TestPass123')
        self.client.force_authenticate(user=other)
        response = self.client.get('/api/v1/expenses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)


class BudgetViewSetTests(APITestCase):
    """Test Budget retrieval and the variance action."""

    def setUp(self):
        self.user = User.objects.create_user(username='budgetview', email='budgetview@example.com', password='TestPass123')
        self.client.force_authenticate(user=self.user)
        self.destination = Destination.objects.create(
            name='Marrakech', country='Morocco', description='Historic medina',
            category=Destination.CategoryChoices.CULTURAL,
            climate=Destination.ClimateChoices.DRY, avg_daily_cost=60,
        )
        self.itinerary = Itinerary.objects.create(
            title='Morocco Trip', destination=self.destination, owner=self.user,
            start_date=date.today(), end_date=date.today() + timedelta(days=6), budget=1200,
        )
        self.budget = Budget.objects.create(
            itinerary=self.itinerary, food_budget=200, accommodation_budget=400,
        )

    def test_list_budgets(self):
        response = self.client.get('/api/v1/budgets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_retrieve_budget_includes_total(self):
        response = self.client.get(f'/api/v1/budgets/{self.budget.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_budget']), 600.0)

    def test_variance_action(self):
        Expense.objects.create(
            itinerary=self.itinerary, category=Expense.CategoryChoices.FOOD,
            description='Tagine dinner', amount=250, date=date.today(),
        )
        response = self.client.get(f'/api/v1/budgets/{self.budget.id}/variance/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        food_row = next(row for row in response.data['breakdown'] if row['category'] == 'food')
        self.assertTrue(food_row['over_budget'])

    def test_other_user_cannot_access_budget(self):
        other = User.objects.create_user(username='budgetintruder', email='intruder@example.com', password='TestPass123')
        self.client.force_authenticate(user=other)
        response = self.client.get(f'/api/v1/budgets/{self.budget.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
