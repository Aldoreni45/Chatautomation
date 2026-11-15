from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pricing.models import ProductPrice
from apps.pricing.management_serializers import (
    PriceManagementSerializer,
    SetProductPriceSerializer,
)
from apps.pricing.services.pricing_service import (
    set_product_price,
)
from apps.stores.models import Store


def get_owned_store(user, store_id):
    store = Store.objects.filter(
        id=store_id,
        owner=user,
        is_active=True,
    ).first()

    if not store:
        raise PermissionDenied(
            "You do not have permission to manage this store."
        )

    return store


class StorePriceListAPIView(generics.ListAPIView):
    serializer_class = PriceManagementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_owned_store(
            self.request.user,
            self.kwargs["store_id"],
        )

        return (
            ProductPrice.objects
            .filter(
                product__store=store,
                is_current=True,
            )
            .select_related("product")
            .order_by("product__name")
        )


class SetProductPriceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, store_id, product_id):
        get_owned_store(request.user, store_id)

        serializer = SetProductPriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            price = set_product_price(
                product_id=product_id,
                store_id=store_id,
                selling_price=serializer.validated_data["selling_price"],
                currency=serializer.validated_data["currency"],
            )

        except DjangoValidationError as exc:
            raise ValidationError(exc.messages)

        return Response(
            PriceManagementSerializer(price).data,
            status=status.HTTP_201_CREATED,
        )


class ProductPriceHistoryAPIView(generics.ListAPIView):
    serializer_class = PriceManagementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_owned_store(
            self.request.user,
            self.kwargs["store_id"],
        )

        return (
            ProductPrice.objects
            .filter(
                product_id=self.kwargs["product_id"],
                product__store=store,
            )
            .select_related("product")
            .order_by("-effective_from")
        )