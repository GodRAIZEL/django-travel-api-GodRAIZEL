"""
travel_api URL Configuration.

All API routes are versioned under /api/v1/. ViewSets are wired through a
single DefaultRouter; each app also contributes its own namespaced urls.py
for function-based and class-based views.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from activity_logs.views import ActivityLogViewSet
from bookings.views import AccommodationViewSet, ActivityViewSet, BookingViewSet
from budgets.views import BudgetViewSet, ExpenseViewSet
from destinations.views import DestinationViewSet
from itineraries.views import ItineraryViewSet, TripAnalyticsViewSet
from reviews.views import ReviewViewSet

router = DefaultRouter()
router.register(r'itineraries', ItineraryViewSet, basename='itinerary')
router.register(r'destinations', DestinationViewSet, basename='destination')
router.register(r'accommodations', AccommodationViewSet, basename='accommodation')
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'analytics', TripAnalyticsViewSet, basename='analytics')
router.register(r'activity-logs', ActivityLogViewSet, basename='activity-log')

urlpatterns = [
    path('admin/', admin.site.urls),

    # App-namespaced FBV / CBV routes are matched FIRST. Several of them
    # (e.g. /destinations/search/, /itineraries/search/, /itineraries/create/)
    # sit directly under the same prefix a router-registered ViewSet also
    # owns; the router's detail route is a greedy `<prefix>/<pk>/` pattern
    # that would otherwise swallow "search" or "create" as if it were a
    # primary key before the real view is ever reached. Checking these
    # explicit paths before the router include avoids that collision.
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/itineraries/', include('itineraries.urls')),
    path('api/v1/destinations/', include('destinations.urls')),
    path('api/v1/bookings/', include('bookings.urls')),
    path('api/v1/reviews/', include('reviews.urls')),
    path('api/v1/budgets/', include('budgets.urls')),

    # Versioned API root - ViewSets via router (checked after the app urls
    # above, so it only ever handles what they didn't already match)
    path('api/v1/', include(router.urls)),

    # API schema / documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
