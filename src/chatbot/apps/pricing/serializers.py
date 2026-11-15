from rest_framework import serializers

from apps.pricing.models import ProductPrice


class ProductPriceSerializer(serializers.ModelSerializer):

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

    class Meta:
        model = ProductPrice

        fields = [
            "id",
            "product_id",
            "product_name",
            "sku",
            "unit",
            "selling_price",
            "currency",
            "effective_from",
            "effective_until",
        ]

        read_only_fields = fields