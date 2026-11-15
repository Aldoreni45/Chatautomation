from decimal import Decimal

import pytest


@pytest.mark.django_db
def test_shopmate_test_data(
    owner,
    store,
    customer_profile,
    store_customer,
    product,
    inventory,
    product_price,
):
    assert store.owner == owner

    assert customer_profile.whatsapp_number == "919876543210"

    assert store_customer.store == store

    assert product.name == "Basmati Rice"

    assert inventory.available_quantity == Decimal("50.000")

    assert product_price.selling_price == Decimal("120.00")