
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.models import Store
from apps.products.models import Product
from apps.products.management_serializers import (
    ProductManagementSerializer,
)


def get_owned_store(user, store_id):
    """
    Return a store only if the authenticated user owns it.
    """

    return get_object_or_404(
        Store,
        id=store_id,
        owner=user,
        is_active=True,
    )


class StoreProductListCreateAPIView(generics.ListCreateAPIView):

    serializer_class = ProductManagementSerializer
    permission_classes = [IsAuthenticated]

    def get_store(self):
        return get_owned_store(
            self.request.user,
            self.kwargs["store_id"],
        )

    def get_queryset(self):
        store = self.get_store()

        return (
            Product.objects
            .filter(store=store)
            .select_related("store", "category")
            .order_by("name")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["store"] = self.get_store()
        return context

    def perform_create(self, serializer):
        store = self.get_store()

        serializer.save(
            store=store,
        )


class StoreProductDetailAPIView(generics.RetrieveUpdateAPIView):

    serializer_class = ProductManagementSerializer
    permission_classes = [IsAuthenticated]

    lookup_url_kwarg = "product_id"

    def get_store(self):
        return get_owned_store(
            self.request.user,
            self.kwargs["store_id"],
        )

    def get_queryset(self):
        store = self.get_store()

        return (
            Product.objects
            .filter(store=store)
            .select_related("store", "category")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["store"] = self.get_store()
        return context


class StoreProductActivationAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, store_id, product_id, action):

        store = get_owned_store(
            request.user,
            store_id,
        )

        product = get_object_or_404(
            Product,
            id=product_id,
            store=store,
        )

        if action == "activate":
            product.is_active = True
            message = "Product activated successfully."

        elif action == "deactivate":
            product.is_active = False
            message = "Product deactivated successfully."

        else:
            return Response(
                {"detail": "Invalid action."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product.save(
            update_fields=["is_active", "updated_at"]
        )

        return Response(
            {
                "message": message,
                "product_id": product.id,
                "is_active": product.is_active,
            },
            status=status.HTTP_200_OK,
        )

