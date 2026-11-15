
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.stores.models import Store
from apps.inventory.models import Inventory

from apps.inventory.management_serializers import (
    InventoryManagementSerializer,
    StockAdjustmentSerializer,
    ReorderLevelSerializer,
)

from apps.inventory.services.inventory_service import (
    adjust_stock,
    update_reorder_level,
)


def get_owned_store(user, store_id):
    return get_object_or_404(
        Store,
        id=store_id,
        owner=user,
        is_active=True,
    )


def handle_inventory_error(error):
    if hasattr(error, "messages"):
        detail = error.messages
    else:
        detail = str(error)

    raise ValidationError({"detail": detail})


class StoreInventoryListAPIView(generics.ListAPIView):
    """
    List inventory belonging to the authenticated store owner.
    """

    serializer_class = InventoryManagementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_owned_store(
            self.request.user,
            self.kwargs["store_id"],
        )

        return (
            Inventory.objects
            .filter(
                product__store=store,
            )
            .select_related("product", "product__store")
            .order_by("product__name")
        )


class StockAdjustmentAPIView(APIView):
    """
    Receive or reduce physical stock.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, store_id, product_id):

        store = get_owned_store(
            request.user,
            store_id,
        )

        input_serializer = StockAdjustmentSerializer(
            data=request.data
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data

        try:
            inventory = adjust_stock(
                product_id=product_id,
                store_id=store.id,
                quantity_change=data["quantity_change"],
                reason=data["reason"],
            )

            return Response(
                {
                    "message": "Stock adjusted successfully.",
                    "reason": data["reason"],
                    "inventory": InventoryManagementSerializer(
                        inventory
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        except DjangoValidationError as error:
            handle_inventory_error(error)


class ReorderLevelAPIView(APIView):
    """
    Update the low-stock threshold.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, store_id, product_id):

        store = get_owned_store(
            request.user,
            store_id,
        )

        input_serializer = ReorderLevelSerializer(
            data=request.data
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        try:
            inventory = update_reorder_level(
                product_id=product_id,
                store_id=store.id,
                reorder_level=input_serializer.validated_data[
                    "reorder_level"
                ],
            )

            return Response(
                InventoryManagementSerializer(inventory).data,
                status=status.HTTP_200_OK,
            )

        except DjangoValidationError as error:
            handle_inventory_error(error)
