
"""
PostgreSQL concurrency tests for order and pricing services.

These tests require real transaction boundaries and row locking, so
they run with ``transaction=True`` (no wrapping atomic block) and use
threads that each get their own database connection.

They are meaningful only on PostgreSQL — SQLite would not reproduce
``select_for_update`` behaviour.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.inventory.models import Inventory
from apps.orders.models import Cart, Order
from apps.orders.services.cart_service import add_to_cart
from apps.orders.services.order_service import confirm_order
from apps.pricing.services.pricing_service import set_product_price


def _run_concurrently(funcs):
    """Run callables in threads; return (results, exceptions)."""
    results = []
    exceptions = []

    def wrapped(fn):
        try:
            results.append(fn())
        except Exception as exc:  # collected, asserted by caller
            exceptions.append(exc)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(funcs)) as pool:
        list(pool.map(wrapped, funcs))

    return results, exceptions


@pytest.mark.django_db(transaction=True)
class TestConcurrentOrderConfirmation:

    def test_only_one_order_wins_for_last_stock(
        self, store, product, inventory, store_customer, db
    ):
        inventory = Inventory.objects.get(product=product)
        inventory.available_quantity = Decimal("10.000")
        inventory.reserved_quantity = Decimal("0")
        inventory.save(
            update_fields=["available_quantity", "reserved_quantity"]
        )

        # Two customers each put 8 units in their cart. Both pass the
        # unlocked cart check (sellable = 10 >= 8), so both reach
        # confirm_order — where the locked recheck must serialize them.
        User = get_user_model()
        profiles = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"race_customer_{i}",
                password="TestPassword123!",
            )
            profile = CustomerProfile.objects.create(
                user=user,
                whatsapp_number=f"91955500000{i}",
                display_name=f"Race {i}",
            )
            StoreCustomer.objects.create(
                store=store, customer=profile, is_active=True
            )
            profiles.append(profile)

        # Product needs a price for confirmation.
        from django.utils import timezone
        from apps.pricing.models import ProductPrice
        ProductPrice.objects.create(
            product=product,
            selling_price=Decimal("10.00"),
            currency="INR",
            is_current=True,
            effective_from=timezone.now(),
        )

        for profile in profiles:
            add_to_cart(
                profile, store.id, product.id, Decimal("8.000")
            )

        results, exceptions = _run_concurrently(
            [
                lambda p=p: confirm_order(p, store.id)
                for p in profiles
            ]
        )

        successes = [o for o in results if o is not None]
        failures = [
            e for e in exceptions
            if isinstance(e, ValidationError)
        ]

        # Exactly one confirmation may succeed; the loser must get a
        # ValidationError (insufficient stock or no active cart).
        assert len(successes) == 1
        assert len(failures) == 1
        assert Order.objects.count() == 1

        inventory.refresh_from_db()
        # Invariant: reserved never exceeds available, physical >= 0.
        assert inventory.reserved_quantity == Decimal("8.000")
        assert inventory.available_quantity == Decimal("10.000")
        assert inventory.reserved_quantity <= inventory.available_quantity

    def test_same_customer_double_confirm_is_safe(
        self, customer_profile, store, product, inventory,
        product_price, store_customer, db
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("2.000")
        )

        results, exceptions = _run_concurrently(
            [
                lambda: confirm_order(customer_profile, store.id),
                lambda: confirm_order(customer_profile, store.id),
            ]
        )

        successes = [o for o in results if o is not None]
        assert len(successes) == 1
        assert Order.objects.count() == 1

        # The cart must be CONVERTED exactly once.
        cart = Cart.objects.get(
            customer=customer_profile.user, store=store
        )
        assert cart.status == Cart.Status.CONVERTED


@pytest.mark.django_db(transaction=True)
class TestConcurrentPriceUpdates:

    def test_concurrent_price_changes_keep_single_current(
        self, product, product_price, db
    ):
        results, exceptions = _run_concurrently(
            [
                lambda: set_product_price(
                    product_id=product.id,
                    store_id=product.store_id,
                    selling_price=Decimal("111.00"),
                    currency="INR",
                ),
                lambda: set_product_price(
                    product_id=product.id,
                    store_id=product.store_id,
                    selling_price=Decimal("222.00"),
                    currency="INR",
                ),
            ]
        )

        assert exceptions == []
        assert len(results) == 2

        from apps.pricing.models import ProductPrice
        current = ProductPrice.objects.filter(
            product=product, is_current=True
        )
        assert current.count() == 1
        # Initial fixture price + two updates = 3 historical rows.
        assert ProductPrice.objects.filter(product=product).count() == 3
