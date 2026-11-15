
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import CustomerProfile
from apps.orders.serializers import (
    CartItemInputSerializer,
    CartRemoveInputSerializer,
    CartStoreInputSerializer,
)
from apps.orders.services.cart_service import (
    add_to_cart,
    update_cart_item,
    remove_from_cart,
    get_cart_summary,
)


def get_authenticated_customer(user):
    """
    Get the CustomerProfile belonging to the authenticated user.
    """

    customer = CustomerProfile.objects.filter(
        user=user
    ).first()

    if customer is None:
        raise PermissionDenied(
            "Your account does not have a customer profile."
        )

    return customer


def handle_service_error(error):
    """
    Convert Django validation errors into DRF API errors.
    """

    if hasattr(error, "messages"):
        raise ValidationError({
            "detail": error.messages
        })

    raise ValidationError({
        "detail": str(error)
    })


def serialize_cart_summary(summary):
    """
    Convert CartSummary dataclass into JSON-compatible data.
    """

    return {
        "cart_id": summary.cart_id,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "sku": item.sku,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "unit_price": (
                    str(item.unit_price)
                    if item.unit_price is not None
                    else None
                ),
                "line_total": (
                    str(item.line_total)
                    if item.line_total is not None
                    else None
                ),
                "currency": item.currency,
                "price_status": item.price_status,
            }
            for item in summary.items
        ],
        "subtotal": (
            str(summary.subtotal)
            if summary.subtotal is not None
            else None
        ),
        "currency": summary.currency,
        "pricing_complete": summary.pricing_complete,
        "message": summary.message,
    }


class CartSummaryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        # Validate store ID.
        input_serializer = CartStoreInputSerializer(
            data=request.query_params
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        store_id = input_serializer.validated_data["store_id"]

        # Identify authenticated customer.
        customer = get_authenticated_customer(
            request.user
        )

        try:
            summary = get_cart_summary(
                customer=customer,
                store_id=store_id,
            )

            return Response(
                serialize_cart_summary(summary),
                status=status.HTTP_200_OK,
            )

        except DjangoValidationError as error:
            handle_service_error(error)


class CartItemAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Add a product to the cart.
        """

        input_serializer = CartItemInputSerializer(
            data=request.data
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data

        customer = get_authenticated_customer(
            request.user
        )

        try:
            add_to_cart(
                customer=customer,
                store_id=data["store_id"],
                product_id=data["product_id"],
                quantity=data["quantity"],
            )

            summary = get_cart_summary(
                customer=customer,
                store_id=data["store_id"],
            )

            return Response(
                serialize_cart_summary(summary),
                status=status.HTTP_200_OK,
            )

        except DjangoValidationError as error:
            handle_service_error(error)

    def patch(self, request):
        """
        Update a product's quantity in the cart.
        """

        input_serializer = CartItemInputSerializer(
            data=request.data
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data

        customer = get_authenticated_customer(
            request.user
        )

        try:
            update_cart_item(
                customer=customer,
                store_id=data["store_id"],
                product_id=data["product_id"],
                new_quantity=data["quantity"],
            )

            summary = get_cart_summary(
                customer=customer,
                store_id=data["store_id"],
            )

            return Response(
                serialize_cart_summary(summary),
                status=status.HTTP_200_OK,
            )

        except DjangoValidationError as error:
            handle_service_error(error)

    def delete(self, request):
        """
        Remove a product from the cart.
        """

        input_serializer = CartRemoveInputSerializer(
            data=request.query_params
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data

        customer = get_authenticated_customer(
            request.user
        )

        try:
            remove_from_cart(
                customer=customer,
                store_id=data["store_id"],
                product_id=data["product_id"],
            )

            summary = get_cart_summary(
                customer=customer,
                store_id=data["store_id"],
            )

            return Response(
                serialize_cart_summary(summary),
                status=status.HTTP_200_OK,
            )

        except DjangoValidationError as error:
            handle_service_error(error)
