
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from apps.customers.models import CustomerProfile
from apps.orders.models import Order, OrderItem


@dataclass(frozen=True)
class OrderHistoryItem:
    order_id: int
    order_number: str
    store_name: str
    status: str
    subtotal: Decimal
    currency: str
    item_count: int
    created_at: object


@dataclass(frozen=True)
class OrderDetailItem:
    product_name: str
    sku: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class OrderDetails:
    order_id: int
    order_number: str
    store_name: str
    status: str
    subtotal: Decimal
    currency: str
    created_at: object
    items: tuple[OrderDetailItem, ...]


def get_customer_orders(
    customer: CustomerProfile,
    store_id: int | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[OrderHistoryItem]:
    """
    Return a customer's order history.

    Optional filters:
    - store_id: Show orders from a particular store.
    - status: Show orders with a particular status.
    - limit: Maximum number of orders to return.
    """

    if limit < 1 or limit > 100:
        raise ValidationError(
            "Limit must be between 1 and 100."
        )

    orders = (
        Order.objects
        .filter(customer=customer.user)
        .select_related("store")
        .order_by("-created_at")
    )

    if store_id is not None:
        orders = orders.filter(store_id=store_id)

    if status is not None:
        valid_statuses = [
            choice[0] for choice in Order.Status.choices
        ]

        if status not in valid_statuses:
            raise ValidationError(
                f"Invalid order status: {status}."
            )

        orders = orders.filter(status=status)

    orders = orders[:limit]

    history = []

    for order in orders:
        history.append(
            OrderHistoryItem(
                order_id=order.id,
                order_number=str(order.order_number),
                store_name=order.store.name,
                status=order.status,
                subtotal=order.subtotal,
                currency=order.currency,
                item_count=order.items.count(),
                created_at=order.created_at,
            )
        )

    return history


def get_customer_order_details(
    customer: CustomerProfile,
    order_id: int,
) -> OrderDetails:
    """
    Return complete details of one order.

    A customer can only access their own order.
    """

    order = (
        Order.objects
        .filter(
            id=order_id,
            customer=customer.user,
        )
        .select_related("store")
        .prefetch_related("items")
        .first()
    )

    if order is None:
        raise ValidationError(
            "Order not found or you do not have permission to view it."
        )

    order_items = []

    for item in order.items.all():
        order_items.append(
            OrderDetailItem(
                product_name=item.product_name,
                sku=item.sku,
                unit=item.unit,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
        )

    return OrderDetails(
        order_id=order.id,
        order_number=str(order.order_number),
        store_name=order.store.name,
        status=order.status,
        subtotal=order.subtotal,
        currency=order.currency,
        created_at=order.created_at,
        items=tuple(order_items),
    )
