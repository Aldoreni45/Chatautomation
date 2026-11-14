
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.inventory.services.inventory_service import check_inventory
from apps.orders.models import Cart, CartItem
from apps.pricing.services.pricing_service import calculate_subtotal
from apps.products.models import Product
from apps.stores.models import Store


# ============================================================
# DATA TRANSFER OBJECTS
# ============================================================

@dataclass(frozen=True)
class CartSummaryItem:
    product_id: int
    product_name: str
    sku: str
    quantity: Decimal
    unit: str
    unit_price: Decimal | None
    line_total: Decimal | None
    currency: str | None
    price_status: str


@dataclass(frozen=True)
class CartSummary:
    cart_id: int
    items: tuple
    subtotal: Decimal | None
    currency: str
    pricing_complete: bool
    message: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def validate_quantity(quantity) -> Decimal:
    """
    Convert and validate the requested quantity.
    """

    try:
        value = Decimal(str(quantity))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Invalid product quantity.")

    if not value.is_finite() or value <= 0:
        raise ValidationError(
            "Quantity must be greater than zero."
        )

    return value


def get_or_create_active_cart(
    customer: CustomerProfile,
    store_id: int,
) -> Cart:
    """
    Retrieve an existing active cart or create a new one.

    A customer can have separate carts for different stores.
    """

    store = Store.objects.filter(
        id=store_id,
        is_active=True,
    ).first()

    if store is None:
        raise ValidationError(
            "Store does not exist or is inactive."
        )

    # Verify customer-store relationship.
    relationship_exists = StoreCustomer.objects.filter(
        customer=customer,
        store=store,
        is_active=True,
    ).exists()

    if not relationship_exists:
        raise ValidationError(
            "Customer is not associated with this store."
        )

    cart, created = Cart.objects.get_or_create(
        customer=customer.user,
        store=store,
        status=Cart.Status.ACTIVE,
    )

    return cart


def get_store_product(
    product_id: int,
    store_id: int,
) -> Product:
    """
    Retrieve an active product belonging to the selected store.
    """

    product = Product.objects.filter(
        id=product_id,
        store_id=store_id,
        is_active=True,
    ).first()

    if product is None:
        raise ValidationError(
            "Product does not exist or is unavailable in this store."
        )

    return product


# ============================================================
# ADD TO CART
# ============================================================

@transaction.atomic
def add_to_cart(
    customer: CustomerProfile,
    store_id: int,
    product_id: int,
    quantity: Decimal | int | float | str,
) -> CartItem:
    """
    Add a product to the customer's active cart.

    If the product already exists, increase its quantity.

    Stock is checked but not reserved here.
    """

    requested_quantity = validate_quantity(quantity)

    cart = get_or_create_active_cart(
        customer=customer,
        store_id=store_id,
    )

    product = get_store_product(
        product_id=product_id,
        store_id=store_id,
    )

    # Lock an existing cart item during its update.
    cart_item = (
        CartItem.objects
        .select_for_update()
        .filter(cart=cart, product=product)
        .first()
    )

    total_quantity = requested_quantity

    if cart_item:
        total_quantity += cart_item.quantity

    # Check combined cart quantity against current stock.
    inventory_result = check_inventory(
        product=product,
        requested_quantity=total_quantity,
    )

    if inventory_result.status != "available":
        raise ValidationError(inventory_result.message)

    if cart_item:
        cart_item.quantity = total_quantity
        cart_item.save(
            update_fields=["quantity", "updated_at"]
        )
    else:
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=requested_quantity,
        )

    return cart_item


# ============================================================
# UPDATE CART ITEM
# ============================================================

@transaction.atomic
def update_cart_item(
    customer: CustomerProfile,
    store_id: int,
    product_id: int,
    new_quantity: Decimal | int | float | str,
) -> CartItem:
    """
    Replace an existing cart item's quantity.

    Example:
        Existing quantity = 5 kg
        New quantity = 2 kg
        Final quantity = 2 kg
    """

    quantity = validate_quantity(new_quantity)

    cart = get_or_create_active_cart(
        customer=customer,
        store_id=store_id,
    )

    cart_item = (
        CartItem.objects
        .select_for_update()
        .filter(
            cart=cart,
            product_id=product_id,
            product__store_id=store_id,
            product__is_active=True,
        )
        .select_related("product")
        .first()
    )

    if cart_item is None:
        raise ValidationError(
            "This product is not present in your cart."
        )

    inventory_result = check_inventory(
        product=cart_item.product,
        requested_quantity=quantity,
    )

    if inventory_result.status != "available":
        raise ValidationError(inventory_result.message)

    cart_item.quantity = quantity

    cart_item.save(
        update_fields=["quantity", "updated_at"]
    )

    return cart_item


# ============================================================
# REMOVE FROM CART
# ============================================================

@transaction.atomic
def remove_from_cart(
    customer: CustomerProfile,
    store_id: int,
    product_id: int,
) -> None:
    """
    Remove a product from the customer's active cart.

    Does not create a new cart if one does not exist.
    """

    cart = Cart.objects.filter(
        customer=customer.user,
        store_id=store_id,
        status=Cart.Status.ACTIVE,
    ).first()

    if cart is None:
        raise ValidationError("Your cart is empty.")

    deleted_count, _ = CartItem.objects.filter(
        cart=cart,
        product_id=product_id,
    ).delete()

    if deleted_count == 0:
        raise ValidationError(
            "This product was not found in your cart."
        )


# ============================================================
# GET CART ITEMS
# ============================================================

def get_cart_items(
    customer: CustomerProfile,
    store_id: int,
):
    """
    Retrieve all items from the customer's active cart.
    """

    cart = Cart.objects.filter(
        customer=customer.user,
        store_id=store_id,
        status=Cart.Status.ACTIVE,
    ).first()

    if cart is None:
        return CartItem.objects.none()

    return (
        CartItem.objects
        .filter(cart=cart)
        .select_related("product")
        .order_by("id")
    )


# ============================================================
# CART SUMMARY
# ============================================================

def get_cart_summary(
    customer: CustomerProfile,
    store_id: int,
) -> CartSummary:
    """
    Retrieve the customer's cart and calculate current prices.

    If any product has an unavailable price, the total is None.
    """

    cart = Cart.objects.filter(
        customer=customer.user,
        store_id=store_id,
        status=Cart.Status.ACTIVE,
    ).first()

    if cart is None:
        return CartSummary(
            cart_id=0,
            items=(),
            subtotal=Decimal("0.00"),
            currency="INR",
            pricing_complete=True,
            message="Your cart is empty.",
        )

    cart_items = (
        CartItem.objects
        .filter(cart=cart)
        .select_related("product")
        .order_by("id")
    )

    summary_items = []

    running_total = Decimal("0.00")
    currencies = set()
    pricing_complete = True

    for item in cart_items:

        # Retrieve the current product price.
        price_result = calculate_subtotal(
            product=item.product,
            quantity=item.quantity,
        )

        if price_result.status != "success":

            pricing_complete = False

            summary_items.append(
                CartSummaryItem(
                    product_id=item.product_id,
                    product_name=item.product.name,
                    sku=item.product.sku,
                    quantity=item.quantity,
                    unit=item.product.unit,
                    unit_price=None,
                    line_total=None,
                    currency=None,
                    price_status=price_result.status,
                )
            )

            continue

        currencies.add(price_result.currency)

        summary_items.append(
            CartSummaryItem(
                product_id=item.product_id,
                product_name=item.product.name,
                sku=item.product.sku,
                quantity=item.quantity,
                unit=item.product.unit,
                unit_price=price_result.unit_price,
                line_total=price_result.subtotal,
                currency=price_result.currency,
                price_status="success",
            )
        )

        running_total += price_result.subtotal

    # Avoid combining different currencies into one total.
    if len(currencies) > 1:
        pricing_complete = False

    if not pricing_complete:
        subtotal = None
        currency = next(iter(currencies), "INR")
        message = (
            "Some cart items have unavailable prices "
            "or different currencies. Please review your cart."
        )

    else:
        subtotal = running_total
        currency = next(iter(currencies), "INR")
        message = "Cart summary calculated successfully."

    return CartSummary(
        cart_id=cart.id,
        items=tuple(summary_items),
        subtotal=subtotal,
        currency=currency,
        pricing_complete=pricing_complete,
        message=message,
    )
