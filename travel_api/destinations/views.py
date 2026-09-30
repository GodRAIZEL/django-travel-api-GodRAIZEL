"""
Views for browsing and searching destinations.

Includes one function-based view (personalized recommendations - custom
scoring logic that doesn't fit a generic view), one class-based APIView
(advanced search with ranking) and a read-only ViewSet for normal browsing.
"""
from django.db.models import Avg, Count, Prefetch, Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from .filters import DestinationFilter
from .models import Destination
from .serializers import DestinationDetailSerializer, DestinationListSerializer

WEATHER_BY_CLIMATE = {
    Destination.ClimateChoices.TROPICAL: {'season': 'warm and humid year-round', 'avg_temp_c': 28},
    Destination.ClimateChoices.DRY: {'season': 'hot days, cool nights', 'avg_temp_c': 30},
    Destination.ClimateChoices.TEMPERATE: {'season': 'mild, four distinct seasons', 'avg_temp_c': 18},
    Destination.ClimateChoices.CONTINENTAL: {'season': 'hot summers, cold winters', 'avg_temp_c': 12},
    Destination.ClimateChoices.POLAR: {'season': 'cold most of the year', 'avg_temp_c': -5},
}


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def destination_recommendations(request):
    """
    GET: Return destinations ranked by how well they match the requesting
    user's stated travel_preferences (category list) plus overall rating,
    falling back to top-rated destinations when no preferences are set.
    """
    user = request.user
    categories = user.preferred_categories()

    queryset = Destination.objects.filter(is_active=True).only(
        'id', 'name', 'country', 'category', 'climate', 'avg_daily_cost', 'image'
    ).annotate(
        rating=Avg('reviews__rating'),
        review_count=Count('reviews', distinct=True),
    )

    if categories:
        queryset = queryset.filter(Q(category__in=categories))

    queryset = queryset.order_by('-rating', '-review_count')[:20]
    serializer = DestinationListSerializer(queryset, many=True, context={'request': request})
    return Response({
        'matched_on_preferences': bool(categories),
        'results': serializer.data,
    })


class DestinationSearchView(APIView):
    """
    Advanced destination search with custom ranking.

    GET: search with free-text + numeric filters, ranked by a weighted
    score of rating and popularity rather than plain field ordering.
    POST: persist the given filters as the user's saved search preference.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        query = request.query_params.get('q', '')
        min_cost = request.query_params.get('min_cost')
        max_cost = request.query_params.get('max_cost')

        queryset = Destination.objects.filter(is_active=True)
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(country__icontains=query) | Q(description__icontains=query)
            )
        if min_cost:
            queryset = queryset.filter(avg_daily_cost__gte=min_cost)
        if max_cost:
            queryset = queryset.filter(avg_daily_cost__lte=max_cost)

        queryset = queryset.annotate(
            rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
        ).order_by('-rating', '-review_count', 'avg_daily_cost')

        serializer = DestinationListSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})

    def post(self, request):
        """Save the current search as a reusable preference on the user's profile."""
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication required to save a search.'}, status=401)
        preferences = request.user.travel_preferences or {}
        preferences['saved_search'] = request.data
        request.user.travel_preferences = preferences
        request.user.save(update_fields=['travel_preferences'])
        return Response({'detail': 'Search preferences saved.', 'saved_search': preferences['saved_search']})


class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Browse destinations (read-only for regular users; creation/editing is
    handled separately via the admin site or a future staff-only endpoint).
    """
    queryset = Destination.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DestinationFilter
    search_fields = ['name', 'description', 'country']
    ordering_fields = ['avg_daily_cost', 'name', 'created_at']
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from bookings.models import Accommodation, Activity
        return (
            super()
            .get_queryset()
            .prefetch_related(
                'reviews',
                Prefetch('activities', queryset=Activity.objects.filter(is_available=True)),
                Prefetch('accommodations', queryset=Accommodation.objects.filter(is_available=True)),
            )
            .annotate(rating=Avg('reviews__rating'), review_count=Count('reviews', distinct=True))
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return DestinationListSerializer
        return DestinationDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context

    @action(detail=True, methods=['get'])
    def popular_activities(self, request, pk=None):
        """GET: Most-booked activities at this destination, ranked by booking count."""
        destination = self.get_object()
        activities = destination.activities.filter(is_available=True).annotate(
            booking_count=Count('bookings')
        ).order_by('-booking_count')[:10]
        from bookings.serializers import ActivitySerializer
        serializer = ActivitySerializer(activities, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def weather_info(self, request, pk=None):
        """GET: Seasonal weather summary derived from the destination's climate."""
        destination = self.get_object()
        info = WEATHER_BY_CLIMATE.get(destination.climate, {})
        return Response({
            'destination': destination.name,
            'climate': destination.climate,
            'best_time_to_visit': destination.best_time_to_visit,
            **info,
        })

    @action(detail=True, methods=['get'])
    def reviews_summary(self, request, pk=None):
        """GET: Rating breakdown (count per star) for this destination."""
        destination = self.get_object()
        breakdown = destination.reviews.values('rating').annotate(count=Count('id')).order_by('-rating')
        return Response({
            'average_rating': destination.average_rating,
            'total_reviews': destination.reviews.count(),
            'breakdown': list(breakdown),
        })
