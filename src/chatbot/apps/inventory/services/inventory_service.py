
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
