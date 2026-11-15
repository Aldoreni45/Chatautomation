
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from apps.inventory.models import Inventory
from apps.products.models import Product


@dataclass(frozen=True)
class InventoryCheckResult:
    status: str
    requested_quantity: Decimal
    available_quantity: Decimal
    fulfillable_quantity: Decimal
    shortage_quantity: Decimal
    message: str


def check_inventory(
    product: Product,
    requested_quantity: Decimal | int | float | str,
) -> InventoryCheckResult:
    """
    Check whether a store can fulfil the requested product quantity.

    Status values:
        available
        partially_available
        unavailable
        invalid_quantity
        inventory_missing

    This function checks stock but does NOT reserve or deduct it.
    """

    # STEP 1: Validate requested quantity
    try:
        requested = Decimal(str(requested_quantity))
    except (InvalidOperation, ValueError, TypeError):
        requested = Decimal("0")

    if not requested.is_finite() or requested <= 0:
        return InventoryCheckResult(
            status="invalid_quantity",
            requested_quantity=requested,
            available_quantity=Decimal("0"),
            fulfillable_quantity=Decimal("0"),
            shortage_quantity=Decimal("0"),
            message="Please provide a valid positive quantity.",
        )

    # STEP 2: Retrieve actual inventory from the database
    try:
        inventory = Inventory.objects.get(product_id=product.pk)
    except Inventory.DoesNotExist:
        return InventoryCheckResult(
            status="inventory_missing",
            requested_quantity=requested,
            available_quantity=Decimal("0"),
            fulfillable_quantity=Decimal("0"),
            shortage_quantity=requested,
            message="Inventory information is not available for this product.",
        )

    # STEP 3: Calculate sellable quantity
    available = inventory.sellable_quantity

    # STEP 4: Check availability
    if available >= requested:
        return InventoryCheckResult(
            status="available",
            requested_quantity=requested,
            available_quantity=available,
            fulfillable_quantity=requested,
            shortage_quantity=Decimal("0"),
            message="The requested quantity is available.",
        )

    if available > 0:
        return InventoryCheckResult(
            status="partially_available",
            requested_quantity=requested,
            available_quantity=available,
            fulfillable_quantity=available,
            shortage_quantity=requested - available,
            message="Only part of the requested quantity is available.",
        )

    return InventoryCheckResult(
        status="unavailable",
        requested_quantity=requested,
        available_quantity=available,
        fulfillable_quantity=Decimal("0"),
        shortage_quantity=requested,
        message="Sorry, this product is currently out of stock.",
    )



from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import Inventory
from apps.products.models import Product


@transaction.atomic
def adjust_stock(
    product_id: int,
    store_id: int,
    quantity_change: Decimal,
    reason: str,
) -> Inventory:
    """
    Increase or decrease physical stock.

    Positive quantity_change = stock received.
    Negative quantity_change = stock reduction.

    Reserved stock is never modified here.
    """

    # STEP 1: Lock and retrieve the product.
    product = (
        Product.objects
        .select_for_update()
        .filter(
            id=product_id,
            store_id=store_id,
            is_active=True,
        )
        .first()
    )

    if product is None:
        raise ValidationError(
            "Product not found or inactive in this store."
        )

    # STEP 2: Validate the adjustment.
    if not quantity_change.is_finite():
        raise ValidationError(
            "Stock adjustment must be finite."
        )

    if quantity_change == Decimal("0"):
        raise ValidationError(
            "Stock adjustment cannot be zero."
        )

    # STEP 3: Lock existing inventory, if present.
    inventory = (
        Inventory.objects
        .select_for_update()
        .filter(product=product)
        .first()
    )

    # STEP 4: Create initial inventory when necessary.
    if inventory is None:

        if quantity_change < Decimal("0"):
            raise ValidationError(
                "Cannot reduce stock because no inventory record exists."
            )

        inventory = Inventory.objects.create(
            product=product,
            available_quantity=quantity_change,
            reserved_quantity=Decimal("0"),
            reorder_level=Decimal("0"),
        )

        return inventory

    # STEP 5: Calculate the new physical quantity.
    new_quantity = (
        inventory.available_quantity + quantity_change
    )

    # STEP 6: Prevent negative physical stock.
    if new_quantity < Decimal("0"):
        raise ValidationError(
            "Physical stock cannot become negative."
        )

    # STEP 7: Prevent physical stock from falling below reservations.
    if new_quantity < inventory.reserved_quantity:
        raise ValidationError(
            "Physical stock cannot be lower than reserved stock. "
            "Please fulfil or cancel the reserved orders first."
        )

    # STEP 8: Save the updated physical stock.
    inventory.available_quantity = new_quantity

    inventory.save(
        update_fields=[
            "available_quantity",
            "updated_at",
        ]
    )

    return inventory


@transaction.atomic
def update_reorder_level(
    product_id: int,
    store_id: int,
    reorder_level: Decimal,
) -> Inventory:
    """
    Update the low-stock threshold for a product.
    """

    product = (
        Product.objects
        .select_for_update()
        .filter(
            id=product_id,
            store_id=store_id,
            is_active=True,
        )
        .first()
    )

    if product is None:
        raise ValidationError(
            "Product not found or inactive in this store."
        )

    inventory = (
        Inventory.objects
        .select_for_update()
        .filter(product=product)
        .first()
    )

    if inventory is None:
        raise ValidationError(
            "Create an inventory record before setting its reorder level."
        )

    if not reorder_level.is_finite() or reorder_level < Decimal("0"):
        raise ValidationError(
            "Reorder level must be a non-negative finite number."
        )

    inventory.reorder_level = reorder_level

    inventory.save(
        update_fields=[
            "reorder_level",
            "updated_at",
        ]
    )

    return inventory

