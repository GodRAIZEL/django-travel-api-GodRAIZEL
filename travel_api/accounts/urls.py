"""URL routes for authentication and account management."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('password/change/', views.change_password, name='password-change'),
    path('password/reset/', views.request_password_reset, name='password-reset-request'),
    path('password/reset/confirm/', views.confirm_password_reset, name='password-reset-confirm'),
]
