"""URL routes for itinerary FBV/CBV endpoints (the ViewSets are wired in the main router)."""
from django.urls import path

from . import views

app_name = 'itineraries'

urlpatterns = [
    path('search/', views.trip_search, name='trip-search'),
    path('create/', views.ItineraryListCreateView.as_view(), name='itinerary-create'),
    path('<int:trip_id>/report/', views.generate_trip_report, name='trip-report'),
    path('<int:trip_id>/collaborators/', views.TripCollaborationView.as_view(), name='collaborators-add'),
    path(
        '<int:trip_id>/collaborators/<int:user_id>/',
        views.TripCollaborationView.as_view(),
        name='collaborators-manage',
    ),
]
