
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import Product
from apps.pricing.models import ProductPrice
from apps.pricing.serializers import ProductPriceSerializer
from apps.pricing.services.pricing_service import calculate_subtotal


class ProductPriceListAPIView(generics.ListAPIView):

    serializer_class = ProductPriceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):

        now = timezone.now()

        queryset = (
            ProductPrice.objects
            .filter(
                is_current=True,
                effective_from__lte=now,
                product__is_active=True,
                product__store__is_active=True,
            )
            .filter(
                Q(effective_until__isnull=True)
                | Q(effective_until__gt=now)
            )
            .select_related(
                "product",
                "product__store",
            )
        )

        store_id = self.request.query_params.get("store_id")
        product_id = self.request.query_params.get("product_id")

        if store_id:
            if not store_id.isdigit():
                raise ValidationError(
                    {"store_id": "Must be a valid integer."}
                )

            queryset = queryset.filter(
                product__store_id=int(store_id)
            )

        if product_id:
            if not product_id.isdigit():
                raise ValidationError(
                    {"product_id": "Must be a valid integer."}
                )

            queryset = queryset.filter(
                product_id=int(product_id)
            )

        return queryset.order_by("product__name")


class CalculateProductPriceAPIView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):

        product_id = request.query_params.get("product_id")
        quantity_value = request.query_params.get("quantity")

        # STEP 1: Validate product ID.
        if not product_id or not product_id.isdigit():
            raise ValidationError(
                {"product_id": "Provide a valid product ID."}
            )

        # STEP 2: Validate quantity.
        if not quantity_value:
            raise ValidationError(
                {"quantity": "Quantity is required."}
            )

        try:
            quantity = Decimal(quantity_value)
        except (InvalidOperation, ValueError):
            raise ValidationError(
                {"quantity": "Enter a valid decimal quantity."}
            )

        if not quantity.is_finite() or quantity <= Decimal("0"):
            raise ValidationError(
                {"quantity": "Quantity must be a positive finite number."}
            )

        # STEP 3: Retrieve the active product.
        product = (
            Product.objects
            .filter(
                id=int(product_id),
                is_active=True,
                store__is_active=True,
            )
            .first()
        )

        if product is None:
            raise ValidationError(
                {"product_id": "Product not found or inactive."}
            )

        # STEP 4: Reuse the existing pricing service.
        result = calculate_subtotal(
            product=product,
            quantity=quantity,
        )

        # STEP 5: Handle pricing service result.
        if result.status != "success":
            raise ValidationError(
                {"detail": result.message}
            )

        # STEP 6: Return calculated price.
        return Response({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "unit": product.unit,
            "quantity": str(quantity),
            "unit_price": str(result.unit_price),
            "currency": result.currency,
            "subtotal": str(result.subtotal),
        })
