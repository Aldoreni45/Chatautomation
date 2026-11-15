
"""
Concurrency test for customer creation.

Verifies that simultaneous ``get_or_create_customer`` calls for the
same WhatsApp number cannot produce duplicate CustomerProfile rows.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import IntegrityError, connection

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.customers.services.customer_service import (
    get_or_create_customer,
)


@pytest.mark.django_db(transaction=True)
def test_concurrent_customer_creation_single_profile(store, db):
    phone = "919123456789"
    errors = []
    successes = []

    def create():
        try:
            successes.append(
                get_or_create_customer(
                    whatsapp_number=phone,
                    store_id=store.id,
                    display_name="Race",
                )
            )
        except IntegrityError as exc:
            errors.append(exc)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: create(), range(4)))

    # The unique whatsapp_number constraint guarantees a single
    # profile even if some threads lose the creation race.
    assert CustomerProfile.objects.filter(
        whatsapp_number=phone
    ).count() == 1
    assert StoreCustomer.objects.filter(store=store).count() == 1

    # Every thread either succeeded or hit the uniqueness constraint;
    # no other exception type is acceptable.
    assert len(successes) + len(errors) == 4
    assert all(isinstance(e, IntegrityError) for e in errors)
