"""URL routes for booking FBV/CBV endpoints (ViewSets are wired in the main router)."""
from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('bulk-update/', views.bulk_update_bookings, name='bulk-update'),
    path('<int:pk>/manage/', views.BookingDetailView.as_view(), name='booking-detail'),
]
