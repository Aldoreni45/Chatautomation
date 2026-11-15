from decimal import Decimal

from rest_framework import serializers

from apps.pricing.models import ProductPrice


class PriceManagementSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = ProductPrice
        fields = [
            "id",
            "product_id",
            "product_name",
            "sku",
            "selling_price",
            "currency",
            "is_current",
            "effective_from",
            "effective_until",
            "created_at",
        ]
        read_only_fields = fields


class SetProductPriceSerializer(serializers.Serializer):
    selling_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    currency = serializers.RegexField(
        regex=r"^[A-Z]{3}$",
        max_length=3,
        min_length=3,
    )