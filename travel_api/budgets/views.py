"""ViewSets for Budget and Expense management, scoped to itineraries the user can access."""
from django.db import transaction
from django.db.models import F, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from activity_logs.models import ActivityLog
from itineraries.models import Itinerary

from .models import Budget, Expense
from .permissions import IsItineraryOwnerOrCollaborator
from .serializers import BudgetSerializer, ExpenseSerializer


def _visible_itineraries(user):
    return Itinerary.objects.filter(Q(owner=user) | Q(collaborators=user)).distinct()


class BudgetViewSet(viewsets.ModelViewSet):
    """
    Manage per-trip budget allocations. A Budget row is auto-created when
    its Itinerary is created (see ItineraryDetailSerializer.create), so
    'create' here mainly exists for completeness / re-creating a lost row.
    """
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated, IsItineraryOwnerOrCollaborator]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['itinerary']
    ordering_fields = ['created_at']

    def get_queryset(self):
        return Budget.objects.filter(itinerary__in=_visible_itineraries(self.request.user)).select_related(
            'itinerary'
        ).prefetch_related('itinerary__expenses')

    @action(detail=True, methods=['get'])
    def variance(self, request, pk=None):
        """GET: Category-by-category budget vs. actual spend, with over/under flags."""
        budget = self.get_object()
        spent = budget.spent_by_category()
        categories = {
            'accommodation': budget.accommodation_budget,
            'activities': budget.activities_budget,
            'food': budget.food_budget,
            'transport': budget.transport_budget,
            'shopping': budget.shopping_budget,
            'miscellaneous': budget.miscellaneous_budget,
        }
        breakdown = []
        for category, allocated in categories.items():
            actual = spent.get(category, 0) or 0
            breakdown.append({
                'category': category,
                'allocated': allocated,
                'actual': actual,
                'over_budget': actual > allocated,
            })
        return Response({'itinerary': budget.itinerary_id, 'breakdown': breakdown})


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    Log and manage individual expenses. Creating/deleting an expense keeps
    the parent Itinerary's actual_spent total in sync via F expressions,
    inside an atomic transaction.
    """
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsItineraryOwnerOrCollaborator]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['itinerary', 'category']
    search_fields = ['description', 'notes']
    ordering_fields = ['date', 'amount', 'created_at']

    def get_queryset(self):
        return Expense.objects.filter(itinerary__in=_visible_itineraries(self.request.user)).select_related(
            'itinerary'
        )

    @transaction.atomic
    def perform_create(self, serializer):
        expense = serializer.save()
        Itinerary.objects.filter(pk=expense.itinerary_id).update(
            actual_spent=F('actual_spent') + expense.amount
        )
        ActivityLog.record(
            user=self.request.user, action=ActivityLog.ActionChoices.EXPENSE_ADDED,
            description=f'Logged {expense.category} expense: {expense.description} (${expense.amount})',
            itinerary=expense.itinerary,
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        Itinerary.objects.filter(pk=instance.itinerary_id).update(
            actual_spent=F('actual_spent') - instance.amount
        )
        instance.delete()
