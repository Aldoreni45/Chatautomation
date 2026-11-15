
from django.db.models import F, ExpressionWrapper, DecimalField

from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter

from apps.inventory.models import Inventory
from apps.inventory.serializers import InventorySerializer


class InventoryListAPIView(generics.ListAPIView):

    serializer_class = InventorySerializer
    permission_classes = [AllowAny]

    filter_backends = [SearchFilter]

    search_fields = [
        "product__name",
        "product__brand",
        "product__sku",
    ]

    def get_queryset(self):

        queryset = (
            Inventory.objects
            .filter(
                product__is_active=True,
                product__store__is_active=True,
            )
            .select_related(
                "product",
                "product__store",
            )
        )

        store_id = self.request.query_params.get("store_id")
        product_id = self.request.query_params.get("product_id")
        low_stock = self.request.query_params.get("low_stock")

        if store_id:
            if not store_id.isdigit():
                raise ValidationError(
                    {"store_id": "Must be a valid integer."}
                )

            queryset = queryset.filter(
                product__store_id=int(store_id)
            )

        if product_id:
            if not product_id.isdigit():
                raise ValidationError(
                    {"product_id": "Must be a valid integer."}
                )

            queryset = queryset.filter(
                product_id=int(product_id)
            )

        if low_stock is not None:
            if low_stock.lower() not in ["true", "false"]:
                raise ValidationError(
                    {"low_stock": "Use true or false."}
                )

            queryset = queryset.annotate(
                sellable_stock_value=ExpressionWrapper(
                    F("available_quantity") - F("reserved_quantity"),
                    output_field=DecimalField(
                        max_digits=12,
                        decimal_places=3,
                    ),
                )
            )

            if low_stock.lower() == "true":
                queryset = queryset.filter(
                    sellable_stock_value__lte=F("reorder_level")
                )
            else:
                queryset = queryset.filter(
                    sellable_stock_value__gt=F("reorder_level")
                )

        return queryset.order_by("product__name")

 
class InventoryDetailAPIView(generics.RetrieveAPIView):

    serializer_class = InventorySerializer
    permission_classes = [AllowAny]

    lookup_field = "product_id"

    def get_queryset(self):
        return (
            Inventory.objects
            .filter(
                product__is_active=True,
                product__store__is_active=True,
            )
            .select_related(
                "product",
                "product__store",
            )
        )
