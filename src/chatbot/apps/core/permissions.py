
from rest_framework.permissions import BasePermission

from apps.stores.models import Store


class IsStoreOwner(BasePermission):
    """
    Allow access only when the authenticated user
    owns the requested active store.
    """

    message = "You do not have permission to manage this store."

    def has_permission(self, request, view):

        if not request.user or not request.user.is_authenticated:
            return False

        store_id = (
            view.kwargs.get("store_id")
            or request.data.get("store_id")
            or request.query_params.get("store_id")
        )

        if not store_id:
            return False

        try:
            store_id = int(store_id)
        except (TypeError, ValueError):
            return False

        return Store.objects.filter(
            id=store_id,
            owner=request.user,
            is_active=True,
        ).exists()
