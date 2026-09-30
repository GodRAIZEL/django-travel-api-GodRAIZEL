"""
Views for itinerary planning and collaboration.

Includes function-based views (custom search + reporting logic), class-based
views (list/create and collaborator management) and ViewSets (full CRUD plus
custom actions, and a read-only analytics ViewSet).
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from activity_logs.models import ActivityLog
from budgets.models import Expense

from .filters import ItineraryFilter
from .models import Collaboration, Itinerary
from .permissions import (
    CanEditItinerary,
    IsCollaborationAdminOrTripOwner,
    IsTripOwner,
    IsTripOwnerOrCollaborator,
)
from .serializers import (
    CollaborationSerializer,
    ItineraryCreateUpdateSerializer,
    ItineraryDetailSerializer,
    ItineraryListSerializer,
)

User = get_user_model()


def _visible_to(user):
    """Shared queryset base: itineraries a user owns or collaborates on."""
    return Itinerary.objects.filter(
        Q(owner=user) | Q(collaborators=user)
    ).distinct()


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def trip_search(request):
    """
    GET: Search the requesting user's trips with custom filters and a
    simple relevance ranking (upcoming + over-budget trips surfaced first).
    POST: Save the given filters as the user's default search preference.
    """
    if request.method == 'GET':
        query = request.query_params.get('q', '')
        queryset = _visible_to(request.user).select_related('destination', 'owner')

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(description__icontains=query) | Q(destination__name__icontains=query)
            )

        # F expressions: flag trips that are over budget.
        queryset = queryset.annotate(
            budget_variance=F('budget') - F('actual_spent')
        ).order_by('budget_variance', 'start_date')

        serializer = ItineraryListSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})

    # POST: persist search preferences
    preferences = request.user.travel_preferences or {}
    preferences['itinerary_search'] = request.data
    request.user.travel_preferences = preferences
    request.user.save(update_fields=['travel_preferences'])
    return Response({'detail': 'Search preferences saved.'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def generate_trip_report(request, trip_id):
    """
    GET: Generate a comprehensive trip report combining budget, bookings
    and itinerary data - the kind of multi-model aggregation that doesn't
    belong in a plain serializer.
    """
    itinerary = _visible_to(request.user).select_related('destination').filter(id=trip_id).first()
    if not itinerary:
        return Response({'detail': 'Itinerary not found.'}, status=status.HTTP_404_NOT_FOUND)

    bookings_summary = itinerary.bookings.aggregate(
        total_spent=Sum('price'),
        booking_count=Count('id'),
    )
    expenses_by_category = Expense.objects.filter(itinerary=itinerary).values('category').annotate(
        total=Sum('amount')
    ).order_by('-total')

    return Response({
        'itinerary': ItineraryListSerializer(itinerary, context={'request': request}).data,
        'bookings': {
            'total_spent': bookings_summary['total_spent'] or 0,
            'count': bookings_summary['booking_count'] or 0,
        },
        'expenses_by_category': list(expenses_by_category),
        'daily_plan_count': itinerary.daily_plans.count(),
    })


class ItineraryListCreateView(generics.ListCreateAPIView):
    """List the user's own itineraries, or create a new one."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ItineraryFilter
    search_fields = ['title', 'description']
    ordering_fields = ['start_date', 'budget', 'created_at']

    def get_serializer_class(self):
        # The list response uses the lean list serializer (no 'description'
        # field), which is what makes the defer('description') below safe -
        # POST/create still returns the full detail representation.
        if self.request and self.request.method == 'GET':
            return ItineraryListSerializer
        return ItineraryDetailSerializer

    def get_queryset(self):
        # defer('description') - the list serializer never renders the
        # long free-text description, so skip fetching it.
        return Itinerary.objects.filter(owner=self.request.user).select_related(
            'destination', 'owner'
        ).prefetch_related('daily_plans').defer('description')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TripCollaborationView(APIView):
    """Manage trip collaborators - add, update role, remove. Allowed for the trip owner,
    or any collaborator whose own role is 'admin'."""
    permission_classes = [permissions.IsAuthenticated, IsCollaborationAdminOrTripOwner]

    def get_itinerary(self, trip_id):
        itinerary = get_object_or_404(Itinerary, id=trip_id)
        self.check_object_permissions(self.request, itinerary)
        return itinerary

    def post(self, request, trip_id):
        """Add a collaborator with a specific role."""
        itinerary = self.get_itinerary(trip_id)
        user_id = request.data.get('user_id')
        role = request.data.get('role', Collaboration.RoleChoices.VIEWER)
        try:
            collaborator = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        if collaborator == itinerary.owner:
            return Response({'detail': 'Owner cannot be added as a collaborator.'}, status=status.HTTP_400_BAD_REQUEST)
        collaboration, created = Collaboration.objects.get_or_create(
            itinerary=itinerary, user=collaborator, defaults={'role': role}
        )
        if not created:
            return Response({'detail': 'User is already a collaborator.'}, status=status.HTTP_400_BAD_REQUEST)
        ActivityLog.record(
            user=request.user, action=ActivityLog.ActionChoices.COLLABORATOR_ADDED,
            description=f'Added {collaborator.username} as {role} on "{itinerary.title}"',
            itinerary=itinerary,
        )
        return Response(CollaborationSerializer(collaboration).data, status=status.HTTP_201_CREATED)

    def patch(self, request, trip_id, user_id):
        """Update a collaborator's role."""
        itinerary = self.get_itinerary(trip_id)
        collaboration = get_object_or_404(Collaboration, itinerary=itinerary, user_id=user_id)
        role = request.data.get('role')
        if role not in Collaboration.RoleChoices.values:
            return Response({'detail': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)
        collaboration.role = role
        collaboration.save(update_fields=['role'])
        return Response(CollaborationSerializer(collaboration).data)

    def delete(self, request, trip_id, user_id):
        """Remove a collaborator."""
        itinerary = self.get_itinerary(trip_id)
        collaboration = get_object_or_404(Collaboration, itinerary=itinerary, user_id=user_id)
        username = collaboration.user.username
        collaboration.delete()
        ActivityLog.record(
            user=request.user, action=ActivityLog.ActionChoices.COLLABORATOR_REMOVED,
            description=f'Removed {username} from "{itinerary.title}"', itinerary=itinerary,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItineraryViewSet(viewsets.ModelViewSet):
    """Complete CRUD operations for itineraries, plus collaboration-aware custom actions."""
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ItineraryFilter
    search_fields = ['title', 'description', 'destination__name']
    ordering_fields = ['created_at', 'start_date', 'budget']

    def get_queryset(self):
        # Note: combining Sum() over 'bookings' with Count() over
        # 'daily_plans__activities' in one annotate() can double-count on
        # SQLite/MySQL because of the multi-table JOIN fan-out; distinct=True
        # on the Count keeps that one accurate. If you need an exact
        # total_bookings_cost too, prefer a separate .annotate() pass with
        # a Subquery, or compute it in the serializer via the prefetched
        # 'bookings' queryset instead of an aggregate.
        return _visible_to(self.request.user).select_related('destination', 'owner').prefetch_related(
            'daily_plans__activities',
            'bookings__accommodation',
            'bookings__activity',
            Prefetch('collaborations', queryset=Collaboration.objects.select_related('user')),
        ).annotate(
            total_activities=Count('daily_plans__activities', distinct=True),
            total_bookings_cost=Sum('bookings__price'),
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return ItineraryListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ItineraryCreateUpdateSerializer
        return ItineraryDetailSerializer

    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), CanEditItinerary()]
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsTripOwner()]
        if self.action in ['retrieve']:
            return [permissions.IsAuthenticated(), IsTripOwnerOrCollaborator()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        itinerary = serializer.save(owner=self.request.user)
        # Auto-create the linked Budget here too, since the lightweight
        # ItineraryCreateUpdateSerializer (unlike ItineraryDetailSerializer)
        # doesn't override create() to do it itself.
        from budgets.models import Budget
        Budget.objects.get_or_create(itinerary=itinerary)
        ActivityLog.record(
            user=self.request.user, action=ActivityLog.ActionChoices.ITINERARY_CREATED,
            description=f'Created itinerary "{itinerary.title}"', itinerary=itinerary,
        )

    def perform_update(self, serializer):
        changed_fields = list(serializer.validated_data.keys())
        itinerary = serializer.save()
        ActivityLog.record(
            user=self.request.user, action=ActivityLog.ActionChoices.ITINERARY_UPDATED,
            description=f'Updated itinerary "{itinerary.title}"', itinerary=itinerary,
            changed_fields=changed_fields,
        )

    def perform_destroy(self, instance):
        ActivityLog.record(
            user=self.request.user, action=ActivityLog.ActionChoices.ITINERARY_DELETED,
            description=f'Deleted itinerary "{instance.title}"',
        )
        instance.delete()

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """POST: Duplicate an existing itinerary (and its daily plans) for a new trip."""
        original = self.get_object()
        clone = Itinerary.objects.create(
            title=f"{original.title} (Copy)",
            description=original.description,
            destination=original.destination,
            owner=request.user,
            start_date=original.start_date,
            end_date=original.end_date,
            budget=original.budget,
        )
        for plan in original.daily_plans.all():
            new_plan = clone.daily_plans.create(
                day_number=plan.day_number, date=plan.date, title=plan.title, notes=plan.notes
            )
            new_plan.activities.set(plan.activities.all())
        return Response(
            ItineraryDetailSerializer(clone, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def export_pdf(self, request, pk=None):
        """GET: Return a lightweight text/JSON export of the itinerary (see README for a
        full PDF-rendering pipeline you can swap in, e.g. WeasyPrint or reportlab)."""
        itinerary = self.get_object()
        lines = [f"Itinerary: {itinerary.title}", f"Destination: {itinerary.destination.name}",
                 f"Dates: {itinerary.start_date} - {itinerary.end_date}"]
        for plan in itinerary.daily_plans.all():
            lines.append(f"Day {plan.day_number} ({plan.date}): {plan.title}")
        from django.http import HttpResponse
        response = HttpResponse('\n'.join(lines), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="itinerary_{itinerary.id}.txt"'
        return response

    @action(detail=True, methods=['post'], url_path='share')
    def share_with_user(self, request, pk=None):
        """POST: Share this itinerary with another user by email, at a given role."""
        itinerary = self.get_object()
        if itinerary.owner != request.user:
            return Response({'detail': 'Only the owner can share this itinerary.'}, status=status.HTTP_403_FORBIDDEN)
        email = request.data.get('email')
        role = request.data.get('role', Collaboration.RoleChoices.VIEWER)
        collaborator = User.objects.filter(email__iexact=email).first()
        if not collaborator:
            return Response({'detail': 'No user found with that email.'}, status=status.HTTP_404_NOT_FOUND)
        collaboration, created = Collaboration.objects.get_or_create(
            itinerary=itinerary, user=collaborator, defaults={'role': role}
        )
        if not created:
            return Response({'detail': 'User is already a collaborator.'}, status=status.HTTP_400_BAD_REQUEST)
        ActivityLog.record(
            user=request.user, action=ActivityLog.ActionChoices.COLLABORATOR_ADDED,
            description=f'Shared "{itinerary.title}" with {collaborator.username} ({role})',
            itinerary=itinerary,
        )
        return Response(CollaborationSerializer(collaboration).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='upcoming')
    def upcoming_trips(self, request):
        """GET: The user's upcoming trips (start date in the future), soonest first."""
        from django.utils import timezone
        queryset = self.get_queryset().filter(start_date__gte=timezone.now().date()).order_by('start_date')
        serializer = ItineraryListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class TripAnalyticsViewSet(viewsets.ViewSet):
    """Read-only trip analytics and statistics (a custom, non-model-backed ViewSet)."""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """GET: Overall statistics across all of the user's trips."""
        queryset = _visible_to(request.user)
        stats = queryset.aggregate(
            total_trips=Count('id'),
            total_budget=Sum('budget'),
            total_spent=Sum('actual_spent'),
        )
        return Response(stats)

    @action(detail=False, methods=['get'])
    def budget_summary(self, request):
        """GET: Spending broken down by expense category, budget vs. actual, across all trips."""
        itineraries = _visible_to(request.user)
        expenses = Expense.objects.filter(itinerary__in=itineraries).values('category').annotate(
            total=Sum('amount')
        ).order_by('-total')
        totals = itineraries.aggregate(total_budget=Sum('budget'), total_spent=Sum('actual_spent'))
        return Response({
            'total_budget': totals['total_budget'] or 0,
            'total_spent': totals['total_spent'] or 0,
            'by_category': list(expenses),
        })

    @action(detail=False, methods=['get'])
    def destination_preferences(self, request):
        """GET: Which destination categories/climates the user gravitates toward, by trip count."""
        itineraries = _visible_to(request.user).select_related('destination')
        by_category = itineraries.values('destination__category').annotate(count=Count('id')).order_by('-count')
        by_climate = itineraries.values('destination__climate').annotate(count=Count('id')).order_by('-count')
        return Response({'by_category': list(by_category), 'by_climate': list(by_climate)})
