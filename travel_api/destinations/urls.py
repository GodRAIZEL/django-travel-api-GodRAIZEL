"""URL routes for destination search and recommendations (FBV/CBV, not the ViewSet)."""
from django.urls import path

from . import views

app_name = 'destinations'

urlpatterns = [
    path('search/', views.DestinationSearchView.as_view(), name='destination-search'),
    path('recommendations/', views.destination_recommendations, name='destination-recommendations'),
]
