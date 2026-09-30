"""Permission classes for reviews."""
from rest_framework import permissions


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    """Anyone authenticated can read reviews; only the author can edit/delete their own."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user
