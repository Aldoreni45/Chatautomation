"""
Create and seed a dedicated performance-test database.

- Creates ``chatbot_perf`` on the same PostgreSQL server as DATABASE_URL.
- Runs migrations.
- Seeds an owner, a store with products/inventory/prices (via the
  existing ``seed_inventory`` command), and a pool of customer accounts
  that can authenticate via JWT for cart/order load tests.

Never prints secrets. Safe to re-run: the perf database is dropped and
recreated each time.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import environ
import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "chatbot"))

env = environ.Env()
env.read_env(ROOT / ".env")

DATABASE_URL = env("DATABASE_URL")
PERF_DB_NAME = os.environ.get("PERF_DB_NAME", "chatbot_perf")


def perf_url(dbname: str) -> str:
    parts = urlparse(DATABASE_URL)
    return urlunparse(parts._replace(path=f"/{dbname}"))


def recreate_database() -> None:
    maintenance_url = perf_url("postgres")
    with psycopg.connect(maintenance_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (PERF_DB_NAME,),
            )
            cur.execute(
                f'DROP DATABASE IF EXISTS "{PERF_DB_NAME}"'
            )
            cur.execute(f'CREATE DATABASE "{PERF_DB_NAME}"')
    print(f"[setup] database '{PERF_DB_NAME}' recreated")


def main() -> None:
    recreate_database()

    # Point Django at the perf database before settings are imported.
    os.environ["DATABASE_URL"] = perf_url(PERF_DB_NAME)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    from apps.customers.models import CustomerProfile, StoreCustomer
    from apps.stores.models import Store

    call_command("migrate", interactive=False, verbosity=0)
    print("[setup] migrations applied")

    User = get_user_model()

    owner, _ = User.objects.get_or_create(
        username="perf_owner",
        defaults={"email": "perf_owner@example.com"},
    )
    owner.set_password("PerfOwner123!")
    owner.is_active = True
    owner.save()

    call_command("seed_inventory", owner="perf_owner")
    print("[setup] store/products/inventory/prices seeded")

    store = Store.objects.get(name="Aldo's Supermarket")

    customer_count = int(os.environ.get("PERF_CUSTOMER_COUNT", "50"))
    for i in range(1, customer_count + 1):
        username = f"perf_cust_{i:02d}"
        user, _ = User.objects.get_or_create(username=username)
        user.set_password("PerfCustomer123!")
        user.is_active = True
        user.save()

        profile, _ = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                "whatsapp_number": f"91900000{i:04d}",
                "display_name": f"Perf Customer {i}",
            },
        )

        StoreCustomer.objects.get_or_create(
            store=store,
            customer=profile,
            defaults={"is_active": True},
        )

    product_count = store.products.filter(is_active=True).count()
    print(
        f"[setup] done. store_id={store.id} "
        f"customers={customer_count} active_products={product_count}"
    )
    print(f"[setup] owner login: perf_owner / PerfOwner123!")
    print(f"[setup] customer logins: perf_cust_01..{customer_count:02d} "
          f"/ PerfCustomer123!")


if __name__ == "__main__":
    main()
