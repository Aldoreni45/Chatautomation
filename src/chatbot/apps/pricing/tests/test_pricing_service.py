
from datetime import timedelta
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.pricing.models import ProductPrice
from apps.pricing.services.pricing_service import (
    calculate_subtotal,
    set_product_price,
)


@pytest.mark.django_db
class TestCalculateSubtotal:

    def test_success(self, product, product_price):
        result = calculate_subtotal(product, Decimal("2.000"))

        assert result.status == "success"
        assert result.quantity == Decimal("2")
        assert result.unit_price == Decimal("120.00")
        assert result.subtotal == Decimal("240.00")
        assert result.currency == "INR"

    def test_rounding_half_up(self, product):
        ProductPrice.objects.create(
            product=product,
            selling_price=Decimal("99.99"),
            currency="INR",
            is_current=True,
            effective_from=timezone.now() - timedelta(minutes=1),
        )

        result = calculate_subtotal(product, Decimal("0.005"))

        # 99.99 * 0.005 = 0.49995 -> 0.50 with ROUND_HALF_UP
        assert result.status == "success"
        assert result.subtotal == Decimal("0.50")

    def test_fractional_quantity(self, product, product_price):
        result = calculate_subtotal(product, Decimal("1.500"))

        assert result.status == "success"
        assert result.subtotal == Decimal("180.00")

    def test_invalid_quantities(self, product, product_price):
        for bad in (Decimal("0"), Decimal("-2"), "abc", None):
            result = calculate_subtotal(product, bad)
            assert result.status == "invalid_quantity"
            assert result.subtotal is None

    def test_missing_price(self, product):
        result = calculate_subtotal(product, Decimal("1"))

        assert result.status == "price_unavailable"
        assert result.subtotal is None

    def test_expired_price(self, product):
        now = timezone.now()
        ProductPrice.objects.create(
            product=product,
            selling_price=Decimal("100.00"),
            currency="INR",
            is_current=True,
            effective_from=now - timedelta(days=10),
            effective_until=now - timedelta(days=1),
        )

        result = calculate_subtotal(product, Decimal("1"))

        assert result.status == "price_unavailable"

    def test_future_effective_price(self, product):
        ProductPrice.objects.create(
            product=product,
            selling_price=Decimal("100.00"),
            currency="INR",
            is_current=True,
            effective_from=timezone.now() + timedelta(days=1),
        )

        result = calculate_subtotal(product, Decimal("1"))

        assert result.status == "price_unavailable"

    def test_closed_historical_price_not_used(
        self, product, product_price
    ):
        # product_price fixture is current; close it and add a new one.
        now = timezone.now()
        product_price.is_current = False
        product_price.effective_until = now
        product_price.save(
            update_fields=["is_current", "effective_until"]
        )

        ProductPrice.objects.create(
            product=product,
            selling_price=Decimal("150.00"),
            currency="INR",
            is_current=True,
            effective_from=now,
        )

        result = calculate_subtotal(product, Decimal("1"))

        assert result.status == "success"
        assert result.unit_price == Decimal("150.00")


@pytest.mark.django_db
class TestSetProductPrice:

    def test_initial_price_creation(self, product):
        price = set_product_price(
            product_id=product.id,
            store_id=product.store_id,
            selling_price=Decimal("99.99"),
            currency="INR",
        )

        assert price.is_current is True
        assert price.selling_price == Decimal("99.99")
        assert price.currency == "INR"
        assert price.effective_until is None

    def test_price_update_preserves_history(
        self, product, product_price
    ):
        old_id = product_price.id

        new_price = set_product_price(
            product_id=product.id,
            store_id=product.store_id,
            selling_price=Decimal("130.00"),
            currency="INR",
        )

        product_price.refresh_from_db()

        assert product_price.is_current is False
        assert product_price.effective_until is not None
        assert product_price.selling_price == Decimal("120.00")

        assert new_price.is_current is True
        assert new_price.selling_price == Decimal("130.00")
        assert new_price.id != old_id

        assert ProductPrice.objects.filter(product=product).count() == 2
        assert ProductPrice.objects.filter(
            product=product, is_current=True
        ).count() == 1

    def test_successive_updates_keep_single_current(
        self, product, product_price
    ):
        set_product_price(
            product_id=product.id,
            store_id=product.store_id,
            selling_price=Decimal("110.00"),
            currency="INR",
        )
        latest = set_product_price(
            product_id=product.id,
            store_id=product.store_id,
            selling_price=Decimal("125.00"),
            currency="INR",
        )

        assert ProductPrice.objects.filter(
            product=product, is_current=True
        ).count() == 1
        assert latest.selling_price == Decimal("125.00")
        assert ProductPrice.objects.filter(product=product).count() == 3

    def test_currency_change_rejected(
        self, product, product_price
    ):
        with pytest.raises(ValidationError, match="Currency cannot be changed"):
            set_product_price(
                product_id=product.id,
                store_id=product.store_id,
                selling_price=Decimal("120.00"),
                currency="USD",
            )

        product_price.refresh_from_db()
        assert product_price.is_current is True

    def test_invalid_prices_rejected(self, product):
        for bad in (Decimal("0"), Decimal("-5"), Decimal("NaN")):
            with pytest.raises(ValidationError, match="greater than zero"):
                set_product_price(
                    product_id=product.id,
                    store_id=product.store_id,
                    selling_price=bad,
                    currency="INR",
                )

    def test_invalid_currencies_rejected(self, product):
        for bad in ("inr", "IN", "INR1", "12R", ""):
            with pytest.raises(
                ValidationError, match="three-letter uppercase"
            ):
                set_product_price(
                    product_id=product.id,
                    store_id=product.store_id,
                    selling_price=Decimal("10.00"),
                    currency=bad,
                )

    def test_unknown_product_rejected(self, store):
        with pytest.raises(ValidationError, match="does not exist"):
            set_product_price(
                product_id=999999,
                store_id=store.id,
                selling_price=Decimal("10.00"),
                currency="INR",
            )

    def test_wrong_store_rejected(self, product, another_store):
        with pytest.raises(ValidationError, match="does not exist"):
            set_product_price(
                product_id=product.id,
                store_id=another_store.id,
                selling_price=Decimal("10.00"),
                currency="INR",
            )

    def test_inactive_product_rejected(self, product):
        product.is_active = False
        product.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="does not exist"):
            set_product_price(
                product_id=product.id,
                store_id=product.store_id,
                selling_price=Decimal("10.00"),
                currency="INR",
            )

    def test_future_effective_current_price_rejected(
        self, product
    ):
        now = timezone.now()
        ProductPrice.objects.create(
            product=product,
            selling_price=Decimal("100.00"),
            currency="INR",
            is_current=True,
            effective_from=now + timedelta(days=1),
        )

        with pytest.raises(ValidationError, match="effective start time"):
            set_product_price(
                product_id=product.id,
                store_id=product.store_id,
                selling_price=Decimal("110.00"),
                currency="INR",
            )
