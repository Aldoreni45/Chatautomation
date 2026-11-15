"""
One-off query-count measurement against the reusable test database.

Runs inside a rolled-back transaction so no data persists. Prints the
number of SQL queries for each critical read operation.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import environ

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "chatbot"))

env = environ.Env()
env.read_env(ROOT / ".env")

parts = urlparse(env("DATABASE_URL"))
os.environ["DATABASE_URL"] = urlunparse(
    parts._replace(path="/test_postgres")
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from apps.customers.models import CustomerProfile, StoreCustomer  # noqa: E402
from apps.inventory.models import Inventory  # noqa: E402
from apps.orders.models import Cart  # noqa: E402
from apps.orders.services.cart_service import (  # noqa: E402
    add_to_cart,
    get_cart_summary,
)
from apps.orders.services.order_query_service import (  # noqa: E402
    get_customer_order_details,
    get_customer_orders,
)
from apps.orders.services.order_service import confirm_order  # noqa: E402
from apps.pricing.models import ProductPrice  # noqa: E402
from apps.products.models import Category, Product  # noqa: E402
from apps.stores.models import Store  # noqa: E402


def measure(label, fn):
    with CaptureQueriesContext(connection) as ctx:
        result = fn()
    print(f"{label:45s} queries={len(ctx.captured_queries)}")
    return result


def main():
    User = get_user_model()

    with transaction.atomic():
        owner = User.objects.create_user(
            username="mq_owner", password="x"
        )
        customer_user = User.objects.create_user(
            username="mq_customer", password="x"
        )
        store = Store.objects.create(
            owner=owner, name="MQ Store", is_active=True
        )
        category = Category.objects.create(
            store=store, name="Cat"
        )
        product = Product.objects.create(
            store=store, category=category, name="Rice",
            sku="MQ-1", unit=Product.Unit.KG, is_active=True,
        )
        Inventory.objects.create(
            product=product, available_quantity=Decimal("500"),
            reserved_quantity=Decimal("0"),
        )
        ProductPrice.objects.create(
            product=product, selling_price=Decimal("100.00"),
            currency="INR", is_current=True,
            effective_from=timezone.now(),
        )
        profile = CustomerProfile.objects.create(
            user=customer_user, whatsapp_number="919000011111"
        )
        StoreCustomer.objects.create(
            store=store, customer=profile, is_active=True
        )

        add_to_cart(profile, store.id, product.id, Decimal("1"))

        # --- service-level reads ---
        measure(
            "cart_summary (1 item)",
            lambda: get_cart_summary(profile, store.id),
        )

        order = confirm_order(profile, store.id)
        measure(
            "order_details (1 order)",
            lambda: get_customer_order_details(
                customer=profile, order_id=order.id
            ),
        )
        measure(
            "order_history (1 order)",
            lambda: get_customer_orders(profile),
        )

        # Add 4 more orders -> 5 total.
        for _ in range(4):
            add_to_cart(profile, store.id, product.id, Decimal("1"))
            confirm_order(profile, store.id)

        measure(
            "order_history (5 orders)",
            lambda: get_customer_orders(profile),
        )

        # --- API-level reads (AllowAny endpoints) ---
        client = APIClient()
        measure(
            "GET /api/products/",
            lambda: client.get("/api/products/"),
        )
        measure(
            "GET /api/inventory/",
            lambda: client.get("/api/inventory/"),
        )
        measure(
            "GET /api/pricing/",
            lambda: client.get("/api/pricing/"),
        )
        measure(
            "GET /api/pricing/calculate/",
            lambda: client.get(
                "/api/pricing/calculate/",
                {"product_id": product.id, "quantity": "2"},
            ),
        )

        transaction.set_rollback(True)


if __name__ == "__main__":
    main()
