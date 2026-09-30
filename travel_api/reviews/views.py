"""ViewSet for reviews - full CRUD, scoped so users can only edit their own."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from activity_logs.models import ActivityLog

from .models import Review
from .permissions import IsReviewOwnerOrReadOnly
from .serializers import ReviewSerializer


class ReviewViewSet(viewsets.ModelViewSet):
    """
    List/retrieve are open to all authenticated users; create requires
    auth; update/delete are restricted to the review's own author.
    """
    serializer_class = ReviewSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['destination', 'accommodation', 'activity', 'rating']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'rating', 'helpful_count']

    def get_queryset(self):
        return Review.objects.select_related('user', 'destination', 'accommodation', 'activity')

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsReviewOwnerOrReadOnly()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        review = serializer.save(user=self.request.user)
        ActivityLog.record(
            user=self.request.user, action=ActivityLog.ActionChoices.REVIEW_POSTED,
            description=f'Posted review "{review.title}" ({review.rating}/5)',
        )

    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """POST: Increment this review's helpful-vote counter."""
        review = self.get_object()
        count = review.mark_helpful()
        return Response({'helpful_count': count})

    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """GET: All reviews written by the requesting user."""
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
