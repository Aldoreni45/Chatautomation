
from rest_framework import serializers

from apps.orders.models import Order


class OrderConfirmInputSerializer(serializers.Serializer):

    store_id = serializers.IntegerField(
        min_value=1,
    )


class OrderHistoryQuerySerializer(serializers.Serializer):

    store_id = serializers.IntegerField(
        min_value=1,
        required=False,
    )

    status = serializers.ChoiceField(
        choices=Order.Status.choices,
        required=False,
    )

    limit = serializers.IntegerField(
        min_value=1,
        max_value=100,
        default=20,
    )
