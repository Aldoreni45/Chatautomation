
from rest_framework import serializers


class CartItemInputSerializer(serializers.Serializer):

    store_id = serializers.IntegerField(
        min_value=1,
    )

    product_id = serializers.IntegerField(
        min_value=1,
    )

    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=0.001,
    )


class CartStoreInputSerializer(serializers.Serializer):

    store_id = serializers.IntegerField(
        min_value=1,
    )


class CartRemoveInputSerializer(serializers.Serializer):

    store_id = serializers.IntegerField(
        min_value=1,
    )

    product_id = serializers.IntegerField(
        min_value=1,
    )
