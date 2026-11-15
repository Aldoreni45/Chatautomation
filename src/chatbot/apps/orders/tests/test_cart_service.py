
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.customers.models import StoreCustomer
from apps.inventory.models import Inventory
from apps.orders.models import Cart, CartItem
from apps.pricing.models import ProductPrice
from apps.products.models import Product
from apps.orders.services.cart_service import (
    add_to_cart,
    get_cart_items,
    get_or_create_active_cart,
    update_cart_item,
    remove_from_cart,
    get_cart_summary,
)


@pytest.mark.django_db
class TestCartService:

    def test_add_product_to_cart(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        add_to_cart(
            customer=customer_profile,
            store_id=store.id,
            product_id=product.id,
            quantity=Decimal("2.000"),
        )

        cart = Cart.objects.get(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )

        item = CartItem.objects.get(
            cart=cart,
            product=product,
        )

        assert item.quantity == Decimal("2.000")

    def test_add_same_product_increases_quantity(
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

        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            Decimal("3.000"),
        )

        cart = Cart.objects.get(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )

        item = CartItem.objects.get(
            cart=cart,
            product=product,
        )

        assert item.quantity == Decimal("5.000")

    def test_add_more_than_stock_fails(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        with pytest.raises(ValidationError):
            add_to_cart(
                customer_profile,
                store.id,
                product.id,
                Decimal("100.000"),
            )

        assert not Cart.objects.filter(
            customer=customer_profile.user,
            store=store,
        ).exists()

    def test_update_cart_quantity(
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

        update_cart_item(
            customer=customer_profile,
            store_id=store.id,
            product_id=product.id,
            new_quantity=Decimal("4.000"),
        )

        cart = Cart.objects.get(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )

        item = CartItem.objects.get(
            cart=cart,
            product=product,
        )

        assert item.quantity == Decimal("4.000")

    def test_remove_cart_item(
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

        remove_from_cart(
            customer=customer_profile,
            store_id=store.id,
            product_id=product.id,
        )

        assert not CartItem.objects.filter(
            cart__customer=customer_profile.user,
            product=product,
        ).exists()

    def test_cart_does_not_reserve_inventory(
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

        inventory.refresh_from_db()

        assert inventory.available_quantity == Decimal("50.000")
        assert inventory.reserved_quantity == Decimal("0.000")
        assert inventory.sellable_quantity == Decimal("50.000")

    def test_cart_summary_calculates_subtotal(
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

        summary = get_cart_summary(
            customer=customer_profile,
            store_id=store.id,
        )

        assert summary.subtotal == Decimal("240.00")


@pytest.mark.django_db
class TestCartCreation:

    def test_get_or_create_active_cart_reuses_cart(
        self, customer_profile, store, store_customer
    ):
        first = get_or_create_active_cart(customer_profile, store.id)
        second = get_or_create_active_cart(customer_profile, store.id)

        assert first.id == second.id
        assert Cart.objects.filter(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        ).count() == 1

    def test_add_to_cart_creates_cart_and_item(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        item = add_to_cart(
            customer_profile, store.id, product.id, Decimal("1.500")
        )

        assert item.cart.customer == customer_profile.user
        assert item.cart.store == store
        assert item.product == product
        assert item.quantity == Decimal("1.500")


@pytest.mark.django_db
class TestAddToCartValidation:

    def test_invalid_quantities_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        for bad in (Decimal("0"), Decimal("-1"), "abc", None):
            with pytest.raises(ValidationError):
                add_to_cart(
                    customer_profile, store.id, product.id, bad
                )

        assert not CartItem.objects.exists()

    def test_inactive_store_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        store.is_active = False
        store.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="inactive"):
            add_to_cart(
                customer_profile, store.id, product.id, Decimal("1")
            )

    def test_missing_store_customer_relationship_rejected(
        self, customer_profile, store, product, inventory,
        product_price
    ):
        # store_customer fixture intentionally not requested.
        with pytest.raises(ValidationError, match="not associated"):
            add_to_cart(
                customer_profile, store.id, product.id, Decimal("1")
            )

    def test_inactive_store_customer_relationship_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        store_customer.is_active = False
        store_customer.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="not associated"):
            add_to_cart(
                customer_profile, store.id, product.id, Decimal("1")
            )

    def test_inactive_product_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        product.is_active = False
        product.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="unavailable"):
            add_to_cart(
                customer_profile, store.id, product.id, Decimal("1")
            )

    def test_other_store_product_rejected(
        self, customer_profile, store, another_store, product,
        inventory, product_price, store_customer
    ):
        # product belongs to `store`; asking for it under another_store.
        StoreCustomer.objects.create(
            store=another_store,
            customer=customer_profile,
            is_active=True,
        )

        with pytest.raises(ValidationError, match="unavailable"):
            add_to_cart(
                customer_profile, another_store.id, product.id,
                Decimal("1")
            )

    def test_insufficient_stock_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        inventory.available_quantity = Decimal("5.000")
        inventory.save(update_fields=["available_quantity"])

        with pytest.raises(ValidationError):
            add_to_cart(
                customer_profile, store.id, product.id,
                Decimal("10.000")
            )

        assert not CartItem.objects.exists()


@pytest.mark.django_db
class TestUpdateCartItem:

    def _add(self, customer_profile, store, product):
        return add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )

    def test_update_nonexistent_item_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        with pytest.raises(ValidationError, match="not present"):
            update_cart_item(
                customer=customer_profile,
                store_id=store.id,
                product_id=product.id,
                new_quantity=Decimal("3.000"),
            )

    def test_update_invalid_quantity_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        self._add(customer_profile, store, product)

        with pytest.raises(ValidationError):
            update_cart_item(
                customer=customer_profile,
                store_id=store.id,
                product_id=product.id,
                new_quantity=Decimal("0"),
            )

    def test_update_beyond_stock_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        inventory.available_quantity = Decimal("3.000")
        inventory.save(update_fields=["available_quantity"])
        self._add(customer_profile, store, product)

        with pytest.raises(ValidationError):
            update_cart_item(
                customer=customer_profile,
                store_id=store.id,
                product_id=product.id,
                new_quantity=Decimal("10.000"),
            )

        item = CartItem.objects.get(product=product)
        assert item.quantity == Decimal("2.000")


@pytest.mark.django_db
class TestRemoveFromCart:

    def test_remove_from_empty_cart_rejected(
        self, customer_profile, store, store_customer
    ):
        with pytest.raises(ValidationError, match="cart is empty"):
            remove_from_cart(
                customer=customer_profile,
                store_id=store.id,
                product_id=1,
            )

    def test_remove_nonexistent_item_rejected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        # Cart exists but product was never added.
        Cart.objects.create(
            customer=customer_profile.user,
            store=store,
            status=Cart.Status.ACTIVE,
        )

        with pytest.raises(ValidationError, match="not found"):
            remove_from_cart(
                customer=customer_profile,
                store_id=store.id,
                product_id=product.id,
            )

    def test_remove_does_not_create_cart(
        self, customer_profile, store, product, store_customer
    ):
        with pytest.raises(ValidationError):
            remove_from_cart(
                customer=customer_profile,
                store_id=store.id,
                product_id=product.id,
            )

        assert not Cart.objects.filter(
            customer=customer_profile.user
        ).exists()


@pytest.mark.django_db
class TestCartIsolation:

    def test_cart_isolated_between_customers(
        self, customer_profile, store, product, inventory,
        product_price, store_customer, db
    ):
        from django.contrib.auth import get_user_model

        from apps.customers.models import CustomerProfile

        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )

        User = get_user_model()
        other_user = User.objects.create_user(
            username="cart_other_customer",
            password="TestPassword123!",
        )
        other_profile = CustomerProfile.objects.create(
            user=other_user,
            whatsapp_number="919999999999",
            display_name="Other",
        )
        StoreCustomer.objects.create(
            store=store, customer=other_profile, is_active=True
        )

        summary = get_cart_summary(other_profile, store.id)

        assert summary.items == ()
        assert summary.subtotal == Decimal("0.00")
        assert summary.message == "Your cart is empty."

    def test_cart_isolated_between_stores(
        self, customer_profile, store, another_store, product,
        inventory, product_price, store_customer, category, db
    ):
        StoreCustomer.objects.create(
            store=another_store,
            customer=customer_profile,
            is_active=True,
        )
        other_product = Product.objects.create(
            store=another_store,
            category=None,
            name="Other Store Rice",
            sku="OTHER-RICE",
            unit=Product.Unit.KG,
            is_active=True,
        )
        Inventory.objects.create(
            product=other_product,
            available_quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0"),
        )
        ProductPrice.objects.create(
            product=other_product,
            selling_price=Decimal("90.00"),
            currency="INR",
            is_current=True,
            effective_from=timezone.now(),
        )

        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )
        add_to_cart(
            customer_profile, another_store.id, other_product.id,
            Decimal("1.000")
        )

        store_cart = get_cart_summary(customer_profile, store.id)
        other_cart = get_cart_summary(
            customer_profile, another_store.id
        )

        assert store_cart.cart_id != other_cart.cart_id
        assert len(store_cart.items) == 1
        assert store_cart.items[0].product_id == product.id
        assert len(other_cart.items) == 1
        assert other_cart.items[0].product_id == other_product.id


@pytest.mark.django_db
class TestCartSummaryEdgeCases:

    def test_empty_cart_summary(
        self, customer_profile, store, store_customer
    ):
        summary = get_cart_summary(customer_profile, store.id)

        assert summary.cart_id == 0
        assert summary.items == ()
        assert summary.subtotal == Decimal("0.00")
        assert summary.pricing_complete is True
        assert summary.message == "Your cart is empty."

    def test_missing_price_marks_pricing_incomplete(
        self, customer_profile, store, category, inventory,
        product_price, store_customer, db
    ):
        no_price_product = Product.objects.create(
            store=store,
            category=category,
            name="No Price Item",
            sku="NOPRICE-1",
            unit=Product.Unit.PIECE,
            is_active=True,
        )
        Inventory.objects.create(
            product=no_price_product,
            available_quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0"),
        )

        add_to_cart(
            customer_profile, store.id, no_price_product.id,
            Decimal("1.000")
        )

        summary = get_cart_summary(customer_profile, store.id)

        assert summary.pricing_complete is False
        assert summary.subtotal is None
        assert summary.items[0].price_status == "price_unavailable"
        assert summary.items[0].unit_price is None

    def test_multiple_currencies_mark_pricing_incomplete(
        self, customer_profile, store, category, product, inventory,
        product_price, store_customer, db
    ):
        usd_product = Product.objects.create(
            store=store,
            category=category,
            name="Imported Item",
            sku="USD-1",
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

        summary = get_cart_summary(customer_profile, store.id)

        assert summary.pricing_complete is False
        assert summary.subtotal is None
        currencies = {item.currency for item in summary.items}
        assert currencies == {"INR", "USD"}


@pytest.mark.django_db
class TestCartConstraints:

    def test_duplicate_cart_item_rejected_by_db(
        self, cart, cart_item, product
    ):
        with pytest.raises(IntegrityError):
            CartItem.objects.create(
                cart=cart, product=product, quantity=Decimal("1.000")
            )

    def test_one_active_cart_per_customer_store(
        self, customer, store
    ):
        Cart.objects.create(
            customer=customer,
            store=store,
            status=Cart.Status.ACTIVE,
        )

        with pytest.raises(IntegrityError):
            Cart.objects.create(
                customer=customer,
                store=store,
                status=Cart.Status.ACTIVE,
            )

    def test_cart_item_quantity_must_be_positive(self, cart, product):
        with pytest.raises(IntegrityError):
            CartItem.objects.create(
                cart=cart, product=product, quantity=Decimal("0")
            )

    def test_get_cart_items_returns_ordered_queryset(
        self, customer_profile, store, product, inventory,
        product_price, store_customer, db
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("1.000")
        )

        items = list(get_cart_items(customer_profile, store.id))

        assert len(items) == 1
        assert items[0].product_id == product.id
