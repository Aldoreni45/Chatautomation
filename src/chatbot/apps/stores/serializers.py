
from rest_framework import serializers

from apps.stores.models import Store


class StoreSerializer(serializers.ModelSerializer):

    class Meta:
        model = Store

        fields = [
            "id",
            "name",
            "description",
            "address",
            "phone",
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
