
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


from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.pricing.models import ProductPrice
from apps.products.models import Product


@transaction.atomic
def set_product_price(
    product_id: int,
    store_id: int,
    selling_price: Decimal,
    currency: str,
):
    """
    Create the initial price or update an existing price.

    Previous prices are preserved as historical records.
    """

    if not selling_price.is_finite() or selling_price <= 0:
        raise ValidationError("Price must be greater than zero.")

    if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
        raise ValidationError("Currency must be a three-letter uppercase code.")

    # Lock the product to serialize concurrent price changes.
    try:
        product = Product.objects.select_for_update().get(
            id=product_id,
            store_id=store_id,
            is_active=True,
        )
    except Product.DoesNotExist:
        raise ValidationError(
            "Product does not exist or is inactive in this store."
        )

    now = timezone.now()

    # Lock the current price record, if one exists.
    current_prices = list(
        ProductPrice.objects.select_for_update().filter(
            product=product,
            is_current=True,
        )
    )

    if len(current_prices) > 1:
        raise ValidationError(
            "Multiple current prices found. Please fix the price records."
        )

    if current_prices:
        old_price = current_prices[0]

        if old_price.currency != currency:
            raise ValidationError(
                "Currency cannot be changed through a price update."
            )

        if old_price.effective_from >= now:
            raise ValidationError(
                "The existing price has an invalid effective start time."
            )

        # Close the old price without deleting it.
        old_price.is_current = False
        old_price.effective_until = now

        old_price.save(
            update_fields=["is_current", "effective_until"]
        )

    # Create a new price record.
    new_price = ProductPrice.objects.create(
        product=product,
        selling_price=selling_price,
        currency=currency,
        is_current=True,
        effective_from=now,
        effective_until=None,
    )

    return new_price