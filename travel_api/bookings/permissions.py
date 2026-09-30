"""Custom permission classes for bookings."""
from rest_framework import permissions


class IsBookingOwner(permissions.BasePermission):
    """Only the user who made a booking can view/modify/delete it."""

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Read access (list/retrieve) is open to any authenticated user; write
    operations (creating/editing accommodations & activities) are staff-only.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and request.user.is_staff
