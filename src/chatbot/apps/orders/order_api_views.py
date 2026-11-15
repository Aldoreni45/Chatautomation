
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import CustomerProfile
from apps.orders.models import Order, OrderItem
from apps.stores.models import Store

from apps.orders.order_api_serializers import (
    OrderConfirmInputSerializer,
    OrderHistoryQuerySerializer,
)

from apps.orders.services.order_service import (
    confirm_order,
    cancel_order,
    complete_order,
)

from apps.orders.services.order_query_service import (
    get_customer_orders,
    get_customer_order_details,
)


def get_customer_profile(user):
    """
    Identify the customer using the authenticated Django user.
    """

    customer = CustomerProfile.objects.filter(
        user=user
    ).first()

    if customer is None:
        raise PermissionDenied(
            "Your account does not have a customer profile."
        )

    return customer


def handle_django_validation_error(error):
    """
    Convert Django ValidationError into a DRF response.
    """

    if hasattr(error, "messages"):
        detail = error.messages
    else:
        detail = str(error)

    raise ValidationError({
        "detail": detail
    })


def serialize_order(order):
    """
    Convert an Order model instance into JSON-compatible data.
    """

    items = OrderItem.objects.filter(
        order=order
    ).order_by("id")

    return {
        "order_id": order.id,
        "order_number": str(order.order_number),
        "store_id": order.store_id,
        "store_name": order.store.name,
        "status": order.status,
        "subtotal": str(order.subtotal),
        "currency": order.currency,
        "created_at": order.created_at,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "sku": item.sku,
                "unit": item.unit,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "line_total": str(item.line_total),
            }
            for item in items
        ],
    }


class OrderConfirmAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Confirm the authenticated customer's active cart.
        """

        input_serializer = OrderConfirmInputSerializer(
            data=request.data
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        store_id = input_serializer.validated_data["store_id"]

        customer = get_customer_profile(request.user)

        try:
            order = confirm_order(
                customer=customer,
                store_id=store_id,
            )

            return Response(
                serialize_order(order),
                status=status.HTTP_201_CREATED,
            )

        except DjangoValidationError as error:
            handle_django_validation_error(error)


class OrderHistoryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve the authenticated customer's order history.
        """

        input_serializer = OrderHistoryQuerySerializer(
            data=request.query_params
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        filters = input_serializer.validated_data

        customer = get_customer_profile(request.user)

        try:
            orders = get_customer_orders(
                customer=customer,
                store_id=filters.get("store_id"),
                status=filters.get("status"),
                limit=filters["limit"],
            )

            return Response({
                "count": len(orders),
                "orders": [
                    {
                        "order_id": order.order_id,
                        "order_number": order.order_number,
                        "store_name": order.store_name,
                        "status": order.status,
                        "subtotal": str(order.subtotal),
                        "currency": order.currency,
                        "item_count": order.item_count,
                        "created_at": order.created_at,
                    }
                    for order in orders
                ],
            })

        except DjangoValidationError as error:
            handle_django_validation_error(error)


class OrderDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        """
        Retrieve one order belonging to the authenticated customer.
        """

        customer = get_customer_profile(request.user)

        try:
            details = get_customer_order_details(
                customer=customer,
                order_id=order_id,
            )

            return Response({
                "order_id": details.order_id,
                "order_number": details.order_number,
                "store_name": details.store_name,
                "status": details.status,
                "subtotal": str(details.subtotal),
                "currency": details.currency,
                "created_at": details.created_at,
                "items": [
                    {
                        "product_name": item.product_name,
                        "sku": item.sku,
                        "unit": item.unit,
                        "quantity": str(item.quantity),
                        "unit_price": str(item.unit_price),
                        "line_total": str(item.line_total),
                    }
                    for item in details.items
                ],
            })

        except DjangoValidationError as error:
            handle_django_validation_error(error)


class OrderCancelAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        """
        Allow a customer to cancel their own order.
        """

        customer = get_customer_profile(request.user)

        try:
            order = cancel_order(
                order_id=order_id,
                customer=customer,
            )

            return Response({
                "message": "Order cancelled successfully.",
                "order": serialize_order(order),
            })

        except DjangoValidationError as error:
            handle_django_validation_error(error)


class OrderCompleteAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        """
        Only the owner of the order's store can complete it.
        """

        order = (
            Order.objects
            .select_related("store")
            .filter(id=order_id)
            .first()
        )

        if order is None:
            raise NotFound("Order not found.")

        # Verify that the authenticated user owns this store.
        is_store_owner = Store.objects.filter(
            id=order.store_id,
            owner=request.user,
            is_active=True,
        ).exists()

        if not is_store_owner:
            raise PermissionDenied(
                "Only the store owner can complete this order."
            )

        try:
            completed_order = complete_order(
                order_id=order_id,
            )

            return Response({
                "message": "Order completed successfully.",
                "order": serialize_order(completed_order),
            })

        except DjangoValidationError as error:
            handle_django_validation_error(error)
