from rest_framework import serializers

from apps.products.models import Product, Category


class ProductManagementSerializer(serializers.ModelSerializer):

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
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_category(self, category):
        """
        Ensure the category belongs to the same store.
        """

        store = self.context.get("store")

        if store and category.store_id != store.id:
            raise serializers.ValidationError(
                "This category does not belong to this store."
            )

        return category

    def validate_sku(self, value):
        """
        Prevent duplicate SKUs within the same store.
        """

        store = self.context.get("store")

        if store is None:
            return value

        queryset = Product.objects.filter(
            store=store,
            sku=value,
        )

        if self.instance:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "A product with this SKU already exists in this store."
            )

        return value
