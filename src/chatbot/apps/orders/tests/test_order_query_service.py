
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError

from apps.orders.models import Order
from apps.orders.services.cart_service import add_to_cart
from apps.orders.services.order_query_service import (
    get_customer_order_details,
    get_customer_orders,
)
from apps.orders.services.order_service import (
    cancel_order,
    confirm_order,
)
from apps.products.models import Product


@pytest.mark.django_db
class TestOrderQueryService:

    def test_customer_can_access_own_order(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
    ):
        from decimal import Decimal

        from apps.orders.services.cart_service import add_to_cart
        from apps.orders.services.order_service import confirm_order

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

        details = get_customer_order_details(
            customer=customer_profile,
            order_id=order.id,
        )

        assert details is not None

    def test_customer_cannot_access_another_customers_order(
        self,
        customer_profile,
        store,
        product,
        inventory,
        product_price,
        store_customer,
        db,
    ):
        from django.contrib.auth import get_user_model

        from apps.customers.models import CustomerProfile
        from apps.orders.services.cart_service import add_to_cart
        from apps.orders.services.order_service import confirm_order

        User = get_user_model()

        other_user = User.objects.create_user(
            username="other_customer",
            password="TestPassword123!",
        )

        add_to_cart(
            customer_profile,
            store.id,
            product.id,
            "2.000",
        )

        order = confirm_order(
            customer=customer_profile,
            store_id=store.id,
        )

        other_profile = CustomerProfile.objects.create(
            user=other_user,
            whatsapp_number="919876543211",
            display_name="Other Customer",
        )

        with pytest.raises(ValidationError):
            get_customer_order_details(
                customer=other_profile,
                order_id=order.id,
            )


def _place_order(customer_profile, store, product, quantity="1.000"):
    add_to_cart(
        customer_profile, store.id, product.id, Decimal(quantity)
    )
    return confirm_order(customer_profile, store.id)


@pytest.mark.django_db
class TestGetCustomerOrders:

    def test_empty_history(
        self, customer_profile, store, store_customer
    ):
        assert get_customer_orders(customer_profile) == []

    def test_history_item_fields(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = _place_order(
            customer_profile, store, product, "2.000"
        )

        history = get_customer_orders(customer_profile)

        assert len(history) == 1
        item = history[0]
        assert item.order_id == order.id
        assert item.order_number == str(order.order_number)
        assert item.store_name == store.name
        assert item.status == Order.Status.CONFIRMED
        assert item.subtotal == Decimal("240.00")
        assert item.currency == "INR"
        assert item.item_count == 1

    def test_store_id_filter(
        self, customer_profile, store, another_store, product,
        inventory, product_price, store_customer, db
    ):
        from apps.customers.models import StoreCustomer
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.pricing.models import ProductPrice
        from django.utils import timezone

        StoreCustomer.objects.create(
            store=another_store,
            customer=customer_profile,
            is_active=True,
        )
        other_product = Product.objects.create(
            store=another_store,
            name="Other Product",
            sku="OP-1",
            unit=Product.Unit.PIECE,
            is_active=True,
        )
        Inventory.objects.create(
            product=other_product,
            available_quantity=Decimal("10.000"),
            reserved_quantity=Decimal("0"),
        )
        ProductPrice.objects.create(
            product=other_product,
            selling_price=Decimal("10.00"),
            currency="INR",
            is_current=True,
            effective_from=timezone.now(),
        )

        _place_order(customer_profile, store, product)
        _place_order(customer_profile, another_store, other_product)

        filtered = get_customer_orders(
            customer_profile, store_id=store.id
        )

        assert len(filtered) == 1
        assert filtered[0].store_name == store.name

    def test_status_filter(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = _place_order(customer_profile, store, product)
        cancel_order(order_id=order.id, customer=customer_profile)
        _place_order(customer_profile, store, product)

        confirmed = get_customer_orders(
            customer_profile, status=Order.Status.CONFIRMED
        )
        cancelled = get_customer_orders(
            customer_profile, status=Order.Status.CANCELLED
        )

        assert len(confirmed) == 1
        assert len(cancelled) == 1

    def test_invalid_status_rejected(
        self, customer_profile
    ):
        with pytest.raises(ValidationError, match="Invalid order status"):
            get_customer_orders(customer_profile, status="bogus")

    def test_limit_validation(self, customer_profile):
        for bad in (0, -1, 101):
            with pytest.raises(ValidationError, match="between 1 and 100"):
                get_customer_orders(customer_profile, limit=bad)

    def test_limit_respected(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        for _ in range(3):
            _place_order(customer_profile, store, product)

        history = get_customer_orders(customer_profile, limit=2)

        assert len(history) == 2

    def test_other_customer_sees_empty_history(
        self, customer_profile, store, product, inventory,
        product_price, store_customer, db
    ):
        from django.contrib.auth import get_user_model
        from apps.customers.models import CustomerProfile

        _place_order(customer_profile, store, product)

        User = get_user_model()
        other_user = User.objects.create_user(
            username="history_other", password="TestPassword123!"
        )
        other_profile = CustomerProfile.objects.create(
            user=other_user,
            whatsapp_number="919777777777",
            display_name="Other",
        )

        assert get_customer_orders(other_profile) == []


@pytest.mark.django_db
class TestGetCustomerOrderDetails:

    def test_details_include_item_snapshots(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = _place_order(
            customer_profile, store, product, "2.000"
        )

        details = get_customer_order_details(
            customer=customer_profile, order_id=order.id
        )

        assert details.order_id == order.id
        assert details.store_name == store.name
        assert details.status == Order.Status.CONFIRMED
        assert details.subtotal == Decimal("240.00")
        assert len(details.items) == 1

        item = details.items[0]
        assert item.product_name == "Basmati Rice"
        assert item.sku == "RICE-001"
        assert item.unit == Product.Unit.KG
        assert item.quantity == Decimal("2.000")
        assert item.unit_price == Decimal("120.00")
        assert item.line_total == Decimal("240.00")

    def test_nonexistent_order_rejected(self, customer_profile):
        with pytest.raises(ValidationError):
            get_customer_order_details(
                customer=customer_profile, order_id=999999
            )
