"""Custom object-level permission classes for itinerary access control."""
from rest_framework import permissions


class IsTripOwner(permissions.BasePermission):
    """Only the itinerary's owner may act on it."""

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsTripOwnerOrCollaborator(permissions.BasePermission):
    """
    Read access is granted to the owner and any collaborator; write access
    is restricted to the owner.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.owner == request.user or request.user in obj.collaborators.all()
        return obj.owner == request.user


class CanEditItinerary(permissions.BasePermission):
    """
    Role-aware edit permission: the owner can always edit; collaborators
    can edit only if their role is 'editor' or 'admin'.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.owner == request.user or request.user in obj.collaborators.all()
        if obj.owner == request.user:
            return True
        collaboration = obj.collaborations.filter(user=request.user).first()
        return bool(collaboration and collaboration.role in ['editor', 'admin'])


class IsCollaborationAdminOrTripOwner(permissions.BasePermission):
    """Managing collaborators (add/remove/change role) requires owner or admin-role collaborator."""

    def has_object_permission(self, request, view, obj):
        if obj.owner == request.user:
            return True
        collaboration = obj.collaborations.filter(user=request.user).first()
        return bool(collaboration and collaboration.role == 'admin')
