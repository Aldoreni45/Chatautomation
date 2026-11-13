
from dataclasses import dataclass
from decimal import Decimal

from apps.products.models import Product
from apps.products.services.product_service import (
    ProductMatchResult,
    find_product,
)
from apps.inventory.services.inventory_service import (
    InventoryCheckResult,
    check_inventory,
)
from apps.pricing.services.pricing_service import (
    PricingResult,
    calculate_subtotal,
)


@dataclass(frozen=True)
class AvailabilityResult:
    status: str
    product: Product | None = None
    matches: tuple = ()
    inventory: InventoryCheckResult | None = None
    pricing: PricingResult | None = None
    message: str = ""


def check_product_availability(
    store_id: int,
    product_query: str,
    requested_quantity: Decimal | int | float | str,
) -> AvailabilityResult:
    """
    Combine product matching, inventory checking and pricing.

    Possible overall statuses:
        matched
        ambiguous
        not_found
        invalid_quantity
        inventory_missing
        available
        partially_available
        unavailable
        price_unavailable
        invalid_price
    """

    # STEP 1: Identify the product
    match: ProductMatchResult = find_product(
        store_id=store_id,
        query=product_query,
    )

    if match.status != "matched":
        return AvailabilityResult(
            status=match.status,
            matches=match.matches,
            message=match.message,
        )

    product = match.product

    # STEP 2: Check inventory
    inventory_result = check_inventory(
        product=product,
        requested_quantity=requested_quantity,
    )

    # Invalid quantities and missing inventory should stop here.
    if inventory_result.status in {
        "invalid_quantity",
        "inventory_missing",
    }:
        return AvailabilityResult(
            status=inventory_result.status,
            product=product,
            inventory=inventory_result,
            message=inventory_result.message,
        )

    # STEP 3: If nothing can be supplied, do not calculate a charge.
    if inventory_result.fulfillable_quantity <= 0:
        return AvailabilityResult(
            status="unavailable",
            product=product,
            inventory=inventory_result,
            message=inventory_result.message,
        )

    # STEP 4: Calculate price for the fulfillable quantity only.
    pricing_result = calculate_subtotal(
        product=product,
        quantity=inventory_result.fulfillable_quantity,
    )

    if pricing_result.status != "success":
        return AvailabilityResult(
            status=pricing_result.status,
            product=product,
            inventory=inventory_result,
            pricing=pricing_result,
            message=pricing_result.message,
        )

    # STEP 5: Return the combined result.
    return AvailabilityResult(
        status=inventory_result.status,
        product=product,
        inventory=inventory_result,
        pricing=pricing_result,
        message=inventory_result.message,
    )
