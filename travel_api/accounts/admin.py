from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Travel profile', {'fields': ('phone', 'date_of_birth', 'bio', 'profile_picture', 'travel_preferences')}),
    )
