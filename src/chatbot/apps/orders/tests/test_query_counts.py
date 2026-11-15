
"""
Query-count tests for critical read operations.

These tests measure real query counts and expose the N+1 patterns
identified in the audit:

- ``get_customer_orders`` calls ``order.items.count()`` per order.
- Order serialization issues a separate ``OrderItem`` query per order.

They intentionally assert the *growth* of query counts rather than an
optimized absolute number — optimization is deferred to Stage 9.
"""

from decimal import Decimal

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.orders.services.cart_service import (
    add_to_cart,
    get_cart_summary,
)
from apps.orders.services.order_query_service import (
    get_customer_order_details,
    get_customer_orders,
)
from apps.orders.services.order_service import confirm_order


def _place_order(customer_profile, store, product, qty="1.000"):
    add_to_cart(
        customer_profile, store.id, product.id, Decimal(qty)
    )
    return confirm_order(customer_profile, store.id)


@pytest.mark.django_db
class TestServiceQueryCounts:

    def test_cart_summary_query_count_is_bounded(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        add_to_cart(
            customer_profile, store.id, product.id, Decimal("1.000")
        )

        with CaptureQueriesContext(connection) as ctx:
            get_cart_summary(customer_profile, store.id)

        # Cart lookup + items + price lookup per item. With one item
        # this should be a small constant.
        assert len(ctx.captured_queries) <= 10

    def test_order_history_queries_grow_with_order_count(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        _place_order(customer_profile, store, product)

        with CaptureQueriesContext(connection) as ctx_one:
            get_customer_orders(customer_profile)

        for _ in range(4):
            _place_order(customer_profile, store, product)

        with CaptureQueriesContext(connection) as ctx_five:
            get_customer_orders(customer_profile)

        # N+1 exposure: each additional order adds an items.count()
        # query. Five orders must cost more queries than one order.
        assert len(ctx_five.captured_queries) > len(
            ctx_one.captured_queries
        )

    def test_order_details_query_count_is_bounded(
        self, customer_profile, store, product, inventory,
        product_price, store_customer
    ):
        order = _place_order(customer_profile, store, product)

        with CaptureQueriesContext(connection) as ctx:
            get_customer_order_details(
                customer=customer_profile, order_id=order.id
            )

        # Single order + select_related store + prefetched items.
        assert len(ctx.captured_queries) <= 5


@pytest.mark.django_db
class TestApiQueryCounts:

    def test_product_list_query_count(
        self, api_client, product, store
    ):
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get("/api/products/")

        assert response.status_code == 200
        # select_related(category, store) keeps this to ~1-2 queries.
        assert len(ctx.captured_queries) <= 5

    def test_inventory_list_query_count(
        self, api_client, product, inventory, store
    ):
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get("/api/inventory/")

        assert response.status_code == 200
        assert len(ctx.captured_queries) <= 5

    def test_pricing_list_query_count(
        self, api_client, product, product_price, store
    ):
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get("/api/pricing/")

        assert response.status_code == 200
        assert len(ctx.captured_queries) <= 5
