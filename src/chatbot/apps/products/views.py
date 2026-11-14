
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.products.models import Product
from apps.products.serializers import ProductSerializer


class ProductListAPIView(generics.ListAPIView):

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]

    search_fields = [
        "name",
        "brand",
        "sku",
    ]

    ordering_fields = [
        "name",
        "created_at",
    ]

    ordering = ["name"]

    def get_queryset(self):
        queryset = (
            Product.objects
            .filter(is_active=True)
            .select_related("category", "store")
        )

        store_id = self.request.query_params.get("store_id")
        category_id = self.request.query_params.get("category_id")

        if store_id:
            queryset = queryset.filter(store_id=store_id)

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset
