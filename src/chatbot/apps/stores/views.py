
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.models import Store
from apps.stores.serializers import StoreSerializer


class StoreListCreateAPIView(generics.ListCreateAPIView):
    """
    GET:
        List stores belonging to the authenticated owner.

    POST:
        Create a store for the authenticated owner.
    """

    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Store.objects.filter(
            owner=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user
        )


class StoreDetailAPIView(generics.RetrieveUpdateAPIView):
    """
    GET:
        Retrieve one store.

    PUT:
        Replace editable store information.

    PATCH:
        Partially update store information.
    """

    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Store.objects.filter(
            owner=self.request.user
        )


class StoreDeactivateAPIView(APIView):
    """
    Deactivate a store without deleting its records.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, store_id):

        store = get_object_or_404(
            Store,
            id=store_id,
            owner=request.user,
        )

        if not store.is_active:
            return Response(
                {"message": "Store is already inactive."},
                status=status.HTTP_200_OK,
            )

        store.is_active = False

        store.save(
            update_fields=["is_active", "updated_at"]
        )

        return Response(
            {
                "message": "Store deactivated successfully.",
                "store_id": store.id,
                "is_active": store.is_active,
            },
            status=status.HTTP_200_OK,
        )
