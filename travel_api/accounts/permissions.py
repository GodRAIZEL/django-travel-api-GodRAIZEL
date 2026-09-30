"""Account-related permission helpers."""
from rest_framework import permissions


class IsSelf(permissions.BasePermission):
    """Allow access only when the object *is* the requesting user."""

    def has_object_permission(self, request, view, obj):
        return obj == request.user
