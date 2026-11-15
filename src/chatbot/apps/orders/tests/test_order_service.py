
from datetime import timedelta
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.inventory.models import Inventory
from apps.orders.models import Cart, CartItem, Order, OrderItem
from apps.pricing.models import ProductPrice
from apps.products.models import Product
from apps.orders.services.cart_service import add_to_cart
from apps.orders.services.order_service import (
    confirm_order,
    cancel_order,
    complete_order,
)


@pytest.mark.django_db
class TestOrderService:

    def test_confirm_order_creates_order(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("3.000"),
        )

        order = confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        assert order is not None
        assert order.customer == customer_profile.user
        assert order.store == store
        assert order.status == Order.Status.CONFIRMED

        assert order.items.count() == 1

    def test_confirm_order_reserves_inventory(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("3.000"),
        )

        confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        inventory.refresh_from_db()

        assert inventory.available_quantity == Decimal("50.000")
        assert inventory.reserved_quantity == Decimal("3.000")
        assert inventory.sellable_quantity == Decimal("47.000")

    def test_confirm_order_converts_cart(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("2.000"),
        )

        confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        cart = Cart.objects.get(
            customer=customer_profile.user,
            store=store,
        )

        assert cart.status == Cart.Status.CONVERTED

    def test_order_item_preserves_price_snapshot(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("2.000"),
        )

        order = confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        item = order.items.get()

        assert item.product_name == product.name
        assert item.sku == product.sku
        assert item.unit == product.unit
        assert item.quantity == Decimal("2.000")
        assert item.unit_price == Decimal("120.00")
        assert item.line_total == Decimal("240.00")

    def test_cancel_order_releases_reserved_stock(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("3.000"),
        )

        order = confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        cancel_order(
            order_id=order.id,
            customer=customer_profile,
        )

        inventory.refresh_from_db()
        order.refresh_from_db()

        assert order.status == Order.Status.CANCELLED
        assert inventory.available_quantity == Decimal("50.000")
        assert inventory.reserved_quantity == Decimal("0.000")

    def test_complete_order_reduces_physical_stock(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("3.000"),
        )

        order = confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        complete_order(order_id=order.id)

        inventory.refresh_from_db()
        order.refresh_from_db()

        assert order.status == Order.Status.COMPLETED
        assert inventory.available_quantity == Decimal("47.000")
        assert inventory.reserved_quantity == Decimal("0.000")
        assert inventory.sellable_quantity == Decimal("47.000")

    def test_cannot_confirm_order_without_cart_items(
        self,
        customer_profile,
        store,
        store_customer,
    ):
        with pytest.raises(ValidationError):
            confirm_order(
                customer=customer_profile,
                store_id=store.id,
            )


@pytest.mark.django_db
class TestConfirmOrderValidation:

    def test_no_cart_at_all(
        self, customer_profile, store, store_customer
    ):
        with pytest.raises(ValidationError, match="No active cart"):
            confirm_order(customer_profile, store.id)

    def test_empty_cart_rejected(
        self, customer_profile, store, store_customer
    ):
        Cart.objects.create(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )

        with pytest.raises(ValidationError, match="cart is empty"):
            confirm_order(customer_profile, store.id)

    def test_missing_store_relationship_rejected(
        self, customer_profile, store, product, inventory,
        product_price, db
    ):
        # No store_customer fixture: relationship does not exist.
        cart = Cart.objects.create(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )
        CartItem.objects.create(
            cart=cart, product=product, quantity=Decimal("1.000")
        )

        with pytest.raises(ValidationError, match="not associated"):
            confirm_order(customer_profile, store.id)

    def test_insufficient_stock_at_confirm(
        self, customer_profile, store, product, inventory,
        product_price, store_customer, db
    ):
        # Bypass add_to_cart's check by inserting the item directly.
        cart = Cart.objects.create(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )
        CartItem.objects.create(
            cart=cart, product=product, quantity=Decimal("60.000")
        )

        with pytest.raises(ValidationError, match="Insufficient stock"):
            confirm_order(customer_profile, store.id)

        assert not Order.objects.exists()
        inventory.refresh_from_db()
        assert inventory.reserved_quantity == Decimal("0")

    def test_missing_price_at_confirm(
        self, customer_profile, store, category, store_customer, db
    ):
        no_price_product = Product.objects.create(
            store=store,
            category=category,
            name="Unpriced Item",
            sku="UNPRICED-1",
            unit=Product.Unit.PIECE,
            is_active=True,
        )
        Inventory.objects.create(
            product=no_price_product,
            available_quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0"),
        )

        cart = Cart.objects.create(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )
        CartItem.objects.create(
            cart=cart, product=no_price_product,
            quantity=Decimal("1.000")
        )

        with pytest.raises(ValidationError, match="price not found"):
            confirm_order(customer_profile, store.id)

        assert not Order.objects.exists()

    def test_product_deactivated_before_confirm(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )
        product.is_active = False
        product.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="no longer available"):
            confirm_order(customer_profile, store.id)

        assert not Order.objects.exists()

    def test_mixed_currency_cart_rejected(
        self, customer_profile, store, category, product, inventory,
        product_price, store_customer, db
    ):
        usd_product = Product.objects.create(
            store=store,
            category=category,
            name="USD Item",
            sku="USD-ORDER-1",
            unit=Product.Unit.PIECE,
            is_active=True,
        )
        Inventory.objects.create(
            product=usd_product,
            available_quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0"),
        )
        ProductPrice.objects.create(
            product=usd_product,
            selling_price=Decimal("5.00"),
            currency="USD",
            is_current=True,
            effective_from=timezone.now(),
        )

        add_to_cart(
            customer_profile, store.id, product.id, Decimal("1.000")
        )
        add_to_cart(
            customer_profile, store.id, usd_product.id, Decimal("1.000")
        )

        with pytest.raises(ValidationError, match="same currency"):
            confirm_order(customer_profile, store.id)

        assert not Order.objects.exists()

    def test_confirm_uses_current_price_not_cart_price(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )

        # Price changes after the item was added to the cart.
        from apps.pricing.services.pricing_service import (
            set_product_price,
        )
        set_product_price(
            product_id=product.id,
            store_id=store.id,
            selling_price=Decimal("200.00"),
            currency="INR",
        )

        order = confirm_order(customer_profile, store.id)

        item = order.items.get()
        assert item.unit_price == Decimal("200.00")
        assert item.line_total == Decimal("400.00")
        assert order.subtotal == Decimal("400.00")

    def test_confirm_rolls_back_everything_on_failure(
        self, customer_profile, store, category, product, inventory,
        product_price, store_customer, db
    ):
        no_price_product = Product.objects.create(
            store=store,
            category=category,
            name="Bad Item",
            sku="BAD-1",
            unit=Product.Unit.PIECE,
            is_active=True,
        )
        bad_inventory = Inventory.objects.create(
            product=no_price_product,
            available_quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0"),
        )

        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )
        add_to_cart(
            customer_profile, store.id, no_price_product.id,
            Decimal("1.000")
        )

        with pytest.raises(ValidationError):
            confirm_order(customer_profile, store.id)

        assert not Order.objects.exists()
        assert not OrderItem.objects.exists()

        inventory.refresh_from_db()
        bad_inventory.refresh_from_db()
        assert inventory.reserved_quantity == Decimal("0")
        assert bad_inventory.reserved_quantity == Decimal("0")

        cart = Cart.objects.get(
            customer=customer_profile.user, store=store
        )
        assert cart.status == Cart.Status.ACTIVE


@pytest.mark.django_db
class TestOrderStateTransitions:

    def _confirmed_order(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )
        return confirm_order(customer_profile, store.id)

    def test_cancel_others_order_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer, db
    ):
        from django.contrib.auth import get_user_model

        order = self._confirmed_order(
            customer_profile, store, product, inventory,
            product_price, store_customer
        )

        User = get_user_model()
        other_user = User.objects.create_user(
            username="order_other", password="TestPassword123!"
        )
        other_profile = CustomerProfile.objects.create(
            user=other_user,
            whatsapp_number="919888888888",
            display_name="Other",
        )

        with pytest.raises(ValidationError, match="permission"):
            cancel_order(order_id=order.id, customer=other_profile)

        order.refresh_from_db()
        assert order.status == Order.Status.CONFIRMED

    def test_cancel_completed_order_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = self._confirmed_order(
            customer_profile, store, product, inventory,
            product_price, store_customer
        )
        complete_order(order_id=order.id)

        with pytest.raises(ValidationError, match="cannot be cancelled"):
            cancel_order(order_id=order.id, customer=customer_profile)

    def test_cancel_cancelled_order_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = self._confirmed_order(
            customer_profile, store, product, inventory,
            product_price, store_customer
        )
        cancel_order(order_id=order.id, customer=customer_profile)

        with pytest.raises(ValidationError, match="cannot be cancelled"):
            cancel_order(order_id=order.id, customer=customer_profile)

    def test_complete_cancelled_order_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = self._confirmed_order(
            customer_profile, store, product, inventory,
            product_price, store_customer
        )
        cancel_order(order_id=order.id, customer=customer_profile)

        with pytest.raises(ValidationError, match="Cannot complete"):
            complete_order(order_id=order.id)

    def test_complete_completed_order_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = self._confirmed_order(
            customer_profile, store, product, inventory,
            product_price, store_customer
        )
        complete_order(order_id=order.id)

        with pytest.raises(ValidationError, match="Cannot complete"):
            complete_order(order_id=order.id)

    def test_cancel_nonexistent_order(
        self, customer_profile
    ):
        with pytest.raises(ValidationError, match="not found"):
            cancel_order(order_id=999999, customer=customer_profile)

    def test_complete_nonexistent_order(self):
        with pytest.raises(ValidationError, match="Order not found"):
            complete_order(order_id=999999)


@pytest.mark.django_db
class TestOrderSnapshotsAndTotals:

    def test_snapshot_survives_product_edits(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )
        order = confirm_order(customer_profile, store.id)

        product.name = "Renamed Product"
        product.sku = "NEW-SKU-999"
        product.unit = Product.Unit.PIECE
        product.save(
            update_fields=["name", "sku", "unit"]
        )

        item = order.items.get()
        assert item.product_name == "Basmati Rice"
        assert item.sku == "RICE-001"
        assert item.unit == Product.Unit.KG

    def test_multi_item_subtotal_accuracy(
        self, customer_profile, store, category, product, inventory,
        product_price, store_customer, db
    ):
        second_product = Product.objects.create(
            store=store,
            category=category,
            name="Second Item",
            sku="SECOND-1",
            unit=Product.Unit.PIECE,
            is_active=True,
        )
        Inventory.objects.create(
            product=second_product,
            available_quantity=Decimal("20.000"),
            reserved_quantity=Decimal("0"),
        )
        ProductPrice.objects.create(
            product=second_product,
            selling_price=Decimal("50.00"),
            currency="INR",
            is_current=True,
            effective_from=timezone.now(),
        )

        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )
        add_to_cart(
            customer_profile, store.id, second_product.id,
            Decimal("3.000")
        )

        order = confirm_order(customer_profile, store.id)

        assert order.items.count() == 2
        # 2 * 120.00 + 3 * 50.00 = 240 + 150 = 390
        assert order.subtotal == Decimal("390.00")
        assert order.currency == "INR"

    def test_inventory_invariants_after_full_cycle(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("10.000")
        )
        order = confirm_order(customer_profile, store.id)

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("50.000")
        assert inventory.reserved_quantity == Decimal("10.000")
        assert inventory.reserved_quantity <= inventory.available_quantity

        complete_order(order_id=order.id)

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("40.000")
        assert inventory.reserved_quantity == Decimal("0.000")
        assert inventory.sellable_quantity == Decimal("40.000")
