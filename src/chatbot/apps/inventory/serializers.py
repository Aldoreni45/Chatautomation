
from rest_framework import serializers

from apps.inventory.models import Inventory


class InventorySerializer(serializers.ModelSerializer):

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

    physical_stock = serializers.DecimalField(
        source="available_quantity",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    reserved_stock = serializers.DecimalField(
        source="reserved_quantity",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    sellable_stock = serializers.SerializerMethodField()

    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Inventory

        fields = [
            "product_id",
            "product_name",
            "sku",
            "unit",
            "physical_stock",
            "reserved_stock",
            "sellable_stock",
            "reorder_level",
            "is_low_stock",
            "updated_at",
        ]

        read_only_fields = fields

    def get_sellable_stock(self, obj):
        return obj.sellable_quantity

    def get_is_low_stock(self, obj):
        return obj.sellable_quantity <= obj.reorder_level
