
from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import Inventory


class InventoryManagementSerializer(serializers.ModelSerializer):

    product_id = serializers.IntegerField(
        source="product.id",
        read_only=True,
    )

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )

    unit = serializers.CharField(
        source="product.unit",
        read_only=True,
    )

    sellable_quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = Inventory

        fields = [
            "id",
            "product_id",
            "product_name",
            "sku",
            "unit",
            "available_quantity",
            "reserved_quantity",
            "sellable_quantity",
            "reorder_level",
            "updated_at",
        ]

        read_only_fields = fields


class StockAdjustmentSerializer(serializers.Serializer):

    quantity_change = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    reason = serializers.CharField(
        max_length=250,
        trim_whitespace=True,
    )

    def validate_quantity_change(self, value):
        if not value.is_finite() or value == Decimal("0"):
            raise serializers.ValidationError(
                "Stock adjustment must be a non-zero finite quantity."
            )

        return value

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError(
                "Please provide a reason for the stock adjustment."
            )

        return value


class ReorderLevelSerializer(serializers.Serializer):

    reorder_level = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )
