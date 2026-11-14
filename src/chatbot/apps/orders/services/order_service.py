
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.inventory.models import Inventory
from apps.orders.models import Cart, CartItem, Order, OrderItem
from apps.pricing.models import ProductPrice


MONEY_PRECISION = Decimal("0.01")


@transaction.atomic
def confirm_order(
    customer: CustomerProfile,
    store_id: int,
) -> Order:
    """
    Confirm a customer's active cart.

    Operations:
        1. Lock the customer's active cart.
        2. Verify the customer-store relationship.
        3. Lock cart items.
        4. Lock inventory records.
        5. Recheck stock.
        6. Retrieve and lock current prices.
        7. Create order and order-item snapshots.
        8. Reserve inventory.
        9. Convert the cart.

    Everything succeeds together or rolls back together.

    Call this function only after explicit customer confirmation.
    """

    # STEP 1: Lock the active cart.
    cart = (
        Cart.objects
        .select_for_update()
        .filter(
            customer=customer.user,
            store_id=store_id,
            status=Cart.Status.ACTIVE,
        )
        .first()
    )

    if cart is None:
        raise ValidationError("No active cart found.")

    # STEP 2: Verify store-customer relationship.
    relationship_exists = StoreCustomer.objects.filter(
        customer=customer,
        store_id=store_id,
        is_active=True,
    ).exists()

    if not relationship_exists:
        raise ValidationError(
            "Customer is not associated with this store."
        )

    # STEP 3: Lock and retrieve cart items.
    cart_items = list(
        CartItem.objects
        .select_for_update()
        .filter(cart=cart)
        .select_related("product")
        .order_by("product_id")
    )

    if not cart_items:
        raise ValidationError("Your cart is empty.")

    now = timezone.now()

    # STEP 4: Lock inventory rows in a consistent order.
    product_ids = sorted(
        item.product_id for item in cart_items
    )

    inventory_records = {
        inventory.product_id: inventory
        for inventory in (
            Inventory.objects
            .select_for_update()
            .filter(product_id__in=product_ids)
            .order_by("product_id")
        )
    }

    # STEP 5: Validate inventory and prices.
    order_lines = []
    currencies = set()
    order_subtotal = Decimal("0.00")

    for item in cart_items:

        product = item.product

        if (
            not product.is_active
            or product.store_id != store_id
        ):
            raise ValidationError(
                f"{product.name} is no longer available."
            )

        inventory = inventory_records.get(product.id)

        if inventory is None:
            raise ValidationError(
                f"Inventory record missing for {product.name}."
            )

        sellable_quantity = (
            inventory.available_quantity
            - inventory.reserved_quantity
        )

        if sellable_quantity < item.quantity:
            raise ValidationError(
                f"Insufficient stock for {product.name}. "
                f"Available: {sellable_quantity} {product.unit}. "
                f"Requested: {item.quantity} {product.unit}."
            )

        # STEP 6: Lock and retrieve the effective current price.
        price = (
            ProductPrice.objects
            .select_for_update()
            .filter(
                product_id=product.id,
                is_current=True,
                effective_from__lte=now,
            )
            .filter(
                effective_until__isnull=True
            )
            .order_by("-effective_from")
            .first()
        )

        # If the current price has an effective_until date,
        # retrieve an effective price with the same conditions.
        if price is None:
            price = (
                ProductPrice.objects
                .select_for_update()
                .filter(
                    product_id=product.id,
                    is_current=True,
                    effective_from__lte=now,
                    effective_until__gt=now,
                )
                .order_by("-effective_from")
                .first()
            )

        if price is None or price.selling_price <= 0:
            raise ValidationError(
                f"Valid current price not found for {product.name}."
            )

        if not price.selling_price.is_finite():
            raise ValidationError(
                f"Invalid price for {product.name}."
            )

        currency = price.currency
        currencies.add(currency)

        line_total = (
            price.selling_price * item.quantity
        ).quantize(
            MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        order_subtotal += line_total

        order_lines.append({
            "item": item,
            "inventory": inventory,
            "unit_price": price.selling_price,
            "currency": currency,
            "line_total": line_total,
        })

    if len(currencies) != 1:
        raise ValidationError(
            "Products in one order must use the same currency."
        )

    currency = next(iter(currencies))

    order_subtotal = order_subtotal.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    # STEP 7: Create the order.
    order = Order.objects.create(
        customer=customer.user,
        store_id=store_id,
        status=Order.Status.CONFIRMED,
        subtotal=order_subtotal,
        currency=currency,
    )

    # STEP 8: Create order-item snapshots and reserve stock.
    order_items = []

    for line in order_lines:

        item = line["item"]
        product = item.product
        inventory = line["inventory"]

        order_items.append(
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                unit=product.unit,
                quantity=item.quantity,
                unit_price=line["unit_price"],
                line_total=line["line_total"],
            )
        )

        # Reserve stock without deducting physical quantity.
        inventory.reserved_quantity += item.quantity
        inventory.save(
            update_fields=[
                "reserved_quantity",
                "updated_at",
            ]
        )

    OrderItem.objects.bulk_create(order_items)

    # STEP 9: Convert the cart.
    cart.status = Cart.Status.CONVERTED
    cart.save(update_fields=["status", "updated_at"])

    return order



from django.core.exceptions import ValidationError
from django.db import transaction

from apps.customers.models import CustomerProfile
from apps.inventory.models import Inventory
from apps.orders.models import Order, OrderItem


@transaction.atomic
def cancel_order(
    order_id: int,
    customer: CustomerProfile,
) -> Order:
    """
    Cancel an order and release its reserved inventory.

    Rules:
    1. A customer can cancel only their own order.
    2. Only CONFIRMED or PROCESSING orders can be cancelled.
    3. Reserved stock is released.
    4. Physical stock is not changed.
    5. All changes happen in one database transaction.
    """

    # STEP 1: Find and lock this customer's order.
    order = (
        Order.objects
        .select_for_update()
        .filter(
            id=order_id,
            customer=customer.user,
        )
        .first()
    )

    if order is None:
        raise ValidationError(
            "Order not found or you do not have permission to cancel it."
        )

    # STEP 2: Check whether this order can be cancelled.
    cancellable_statuses = [
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
    ]

    if order.status not in cancellable_statuses:
        raise ValidationError(
            f"This order cannot be cancelled. Current status: {order.status}."
        )

    # STEP 3: Retrieve order items in a consistent order.
    order_items = list(
        OrderItem.objects
        .filter(order=order)
        .order_by("product_id")
    )

    if not order_items:
        raise ValidationError(
            "This order has no items. Cancellation cannot continue."
        )

    # STEP 4: Lock the inventory rows for all products.
    product_ids = sorted({
        item.product_id for item in order_items
    })

    inventory_records = {
        inventory.product_id: inventory
        for inventory in (
            Inventory.objects
            .select_for_update()
            .filter(product_id__in=product_ids)
            .order_by("product_id")
        )
    }

    # STEP 5: Check that every product has an inventory record.
    for product_id in product_ids:
        if product_id not in inventory_records:
            raise ValidationError(
                f"Inventory record missing for product ID {product_id}."
            )

    # STEP 6: Release the reserved quantities.
    for item in order_items:
        inventory = inventory_records[item.product_id]

        if inventory.reserved_quantity < item.quantity:
            raise ValidationError(
                f"Cannot release stock for {item.product_name}. "
                "The reserved quantity is lower than the order quantity. "
                "Please check the inventory records."
            )

        inventory.reserved_quantity -= item.quantity

        inventory.save(
            update_fields=[
                "reserved_quantity",
                "updated_at",
            ]
        )

    # STEP 7: Update the order status.
    order.status = Order.Status.CANCELLED

    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return order


from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import Inventory
from apps.orders.models import Order, OrderItem


@transaction.atomic
def complete_order(order_id: int) -> Order:
    """
    Complete an order after the store fulfils it.

    Physical stock decreases.
    Reserved stock decreases.
    Sellable stock remains unchanged.

    All database changes happen atomically.
    """

    # STEP 1: Lock the order.
    order = (
        Order.objects
        .select_for_update()
        .filter(id=order_id)
        .first()
    )

    if order is None:
        raise ValidationError("Order not found.")

    # STEP 2: Validate the order status.
    completable_statuses = [
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
    ]

    if order.status not in completable_statuses:
        raise ValidationError(
            f"Cannot complete this order. "
            f"Current status: {order.status}."
        )

    # STEP 3: Retrieve order items.
    order_items = list(
        OrderItem.objects
        .filter(order=order)
        .order_by("product_id")
    )

    if not order_items:
        raise ValidationError(
            "Cannot complete an order without items."
        )

    # STEP 4: Collect product IDs.
    product_ids = sorted({
        item.product_id for item in order_items
    })

    # STEP 5: Lock all relevant inventory records.
    inventory_records = {
        inventory.product_id: inventory
        for inventory in (
            Inventory.objects
            .select_for_update()
            .filter(product_id__in=product_ids)
            .order_by("product_id")
        )
    }

    # STEP 6: Validate inventory records before changing anything.
    for product_id in product_ids:
        if product_id not in inventory_records:
            raise ValidationError(
                f"Inventory record missing for product ID {product_id}."
            )

    for item in order_items:
        inventory = inventory_records[item.product_id]

        if inventory.reserved_quantity < item.quantity:
            raise ValidationError(
                f"Insufficient reserved stock for {item.product_name}."
            )

        if inventory.available_quantity < item.quantity:
            raise ValidationError(
                f"Insufficient physical stock for {item.product_name}."
            )

    # STEP 7: Deduct physical stock and release reservations.
    for item in order_items:
        inventory = inventory_records[item.product_id]

        inventory.available_quantity -= item.quantity
        inventory.reserved_quantity -= item.quantity

        inventory.save(
            update_fields=[
                "available_quantity",
                "reserved_quantity",
                "updated_at",
            ]
        )

    # STEP 8: Update order status.
    order.status = Order.Status.COMPLETED

    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return order
