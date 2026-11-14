
from rest_framework import serializers

from apps.products.models import Product


class ProductSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
        default=None,
    )

    class Meta:
        model = Product

        fields = [
            "id",
            "name",
            "brand",
            "sku",
            "description",
            "unit",
            "category",
            "category_name",
            "is_active",
        ]

        read_only_fields = fields
