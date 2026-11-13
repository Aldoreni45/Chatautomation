
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from apps.products.models import Product
from apps.pricing.models import ProductPrice


@dataclass(frozen=True)
class PricingResult:
    status: str
    quantity: Decimal
    unit_price: Decimal | None = None
    subtotal: Decimal | None = None
    currency: str = "INR"
    message: str = ""


MONEY_PRECISION = Decimal("0.01")


def calculate_subtotal(
    product: Product,
    quantity: Decimal | int | float | str,
) -> PricingResult:
    """
    Retrieve the current effective price and calculate the subtotal.

    The quantity should be the quantity that can actually be fulfilled,
    not necessarily the quantity originally requested.
    """

    # STEP 1: Validate quantity
    try:
        requested_quantity = Decimal(str(quantity))
    except (InvalidOperation, ValueError, TypeError):
        requested_quantity = Decimal("0")

    if not requested_quantity.is_finite() or requested_quantity <= 0:
        return PricingResult(
            status="invalid_quantity",
            quantity=requested_quantity,
            message="Please provide a valid positive quantity.",
        )

    # STEP 2: Retrieve the effective current price
    now = timezone.now()

    price_record = (
        ProductPrice.objects
        .filter(
            product_id=product.pk,
            is_current=True,
            effective_from__lte=now,
        )
        .filter(
            Q(effective_until__isnull=True)
            | Q(effective_until__gt=now)
        )
        .order_by("-effective_from", "-created_at")
        .first()
    )

    if price_record is None:
        return PricingResult(
            status="price_unavailable",
            quantity=requested_quantity,
            message="No effective current price is available for this product.",
        )

    # STEP 3: Validate the stored price
    unit_price = price_record.selling_price

    if not unit_price.is_finite() or unit_price <= 0:
        return PricingResult(
            status="invalid_price",
            quantity=requested_quantity,
            message="The stored product price is invalid.",
        )

    # STEP 4: Calculate subtotal using Decimal
    subtotal = (unit_price * requested_quantity).quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    # STEP 5: Return structured result
    return PricingResult(
        status="success",
        quantity=requested_quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        currency=price_record.currency,
        message="Price calculated successfully.",
    )
