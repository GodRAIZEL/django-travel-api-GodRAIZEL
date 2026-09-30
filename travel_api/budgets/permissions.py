"""Permission classes for budgets and expenses - scoped to the owning itinerary."""
from rest_framework import permissions


class IsItineraryOwnerOrCollaborator(permissions.BasePermission):
    """
    Only the itinerary's owner or one of its collaborators may view/manage
    its budget and expenses.
    """

    def has_object_permission(self, request, view, obj):
        itinerary = obj.itinerary
        return itinerary.owner == request.user or request.user in itinerary.collaborators.all()
