
from decimal import Decimal

import pytest

from django.core.exceptions import ValidationError

from apps.inventory.models import Inventory
from apps.inventory.services.inventory_service import (
    adjust_stock,
    check_inventory,
    update_reorder_level,
)
from apps.products.models import Product


@pytest.mark.django_db
class TestCheckInventory:

    def test_sufficient_stock(self, product, inventory):
        result = check_inventory(product, Decimal("10.000"))

        assert result.status == "available"
        assert result.requested_quantity == Decimal("10")
        assert result.available_quantity == Decimal("50.000")
        assert result.fulfillable_quantity == Decimal("10")
        assert result.shortage_quantity == Decimal("0")

    def test_exact_sellable_boundary(self, product, inventory):
        result = check_inventory(product, Decimal("50.000"))

        assert result.status == "available"
        assert result.fulfillable_quantity == Decimal("50.000")

    def test_zero_stock(self, product, inventory):
        inventory.available_quantity = Decimal("0")
        inventory.save(update_fields=["available_quantity"])

        result = check_inventory(product, Decimal("5.000"))

        assert result.status == "unavailable"
        assert result.fulfillable_quantity == Decimal("0")
        assert result.shortage_quantity == Decimal("5")

    def test_partial_stock_respects_reserved(self, product, inventory):
        inventory.available_quantity = Decimal("50.000")
        inventory.reserved_quantity = Decimal("30.000")
        inventory.save(
            update_fields=["available_quantity", "reserved_quantity"]
        )

        result = check_inventory(product, Decimal("30.000"))

        assert result.status == "partially_available"
        assert result.available_quantity == Decimal("20.000")
        assert result.fulfillable_quantity == Decimal("20.000")
        assert result.shortage_quantity == Decimal("10")

    def test_reserved_stock_reduces_sellable(self, product, inventory):
        inventory.reserved_quantity = Decimal("40.000")
        inventory.save(update_fields=["reserved_quantity"])

        result = check_inventory(product, Decimal("15.000"))

        assert result.status == "partially_available"
        assert result.available_quantity == Decimal("10.000")

    def test_invalid_quantities(self, product, inventory):
        for bad in (Decimal("0"), Decimal("-1"), "abc", None):
            result = check_inventory(product, bad)
            assert result.status == "invalid_quantity"
            assert result.fulfillable_quantity == Decimal("0")

    def test_non_finite_quantity(self, product, inventory):
        result = check_inventory(product, float("nan"))
        assert result.status == "invalid_quantity"

        result = check_inventory(product, float("inf"))
        assert result.status == "invalid_quantity"

    def test_missing_inventory(self, product):
        # product fixture's inventory is not requested here.
        result = check_inventory(product, Decimal("5.000"))

        assert result.status == "inventory_missing"
        assert result.shortage_quantity == Decimal("5")

    def test_sellable_invariant(self, product, inventory):
        inventory.available_quantity = Decimal("50.000")
        inventory.reserved_quantity = Decimal("20.000")
        inventory.save(
            update_fields=["available_quantity", "reserved_quantity"]
        )
        inventory.refresh_from_db()

        assert (
            inventory.sellable_quantity
            == inventory.available_quantity
            - inventory.reserved_quantity
        )
        assert inventory.sellable_quantity == Decimal("30.000")


@pytest.mark.django_db
class TestAdjustStock:

    def test_positive_adjustment(self, product, inventory):
        updated = adjust_stock(
            product_id=product.id,
            store_id=product.store_id,
            quantity_change=Decimal("10.000"),
            reason="Restock",
        )

        assert updated.available_quantity == Decimal("60.000")
        assert updated.reserved_quantity == Decimal("0")

    def test_negative_adjustment(self, product, inventory):
        updated = adjust_stock(
            product_id=product.id,
            store_id=product.store_id,
            quantity_change=Decimal("-15.000"),
            reason="Damage",
        )

        assert updated.available_quantity == Decimal("35.000")

    def test_zero_adjustment_rejected(self, product, inventory):
        with pytest.raises(ValidationError, match="cannot be zero"):
            adjust_stock(
                product_id=product.id,
                store_id=product.store_id,
                quantity_change=Decimal("0"),
                reason="No-op",
            )

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("50.000")

    def test_negative_physical_stock_prevented(self, product, inventory):
        with pytest.raises(ValidationError, match="cannot become negative"):
            adjust_stock(
                product_id=product.id,
                store_id=product.store_id,
                quantity_change=Decimal("-60.000"),
                reason="Oversell",
            )

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("50.000")

    def test_reduction_below_reserved_prevented(
        self, product, inventory
    ):
        inventory.reserved_quantity = Decimal("30.000")
        inventory.save(update_fields=["reserved_quantity"])

        with pytest.raises(ValidationError, match="reserved stock"):
            adjust_stock(
                product_id=product.id,
                store_id=product.store_id,
                quantity_change=Decimal("-25.000"),
                reason="Below reservation",
            )

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("50.000")
        assert inventory.reserved_quantity == Decimal("30.000")

    def test_adjustment_never_touches_reserved(
        self, product, inventory
    ):
        inventory.reserved_quantity = Decimal("10.000")
        inventory.save(update_fields=["reserved_quantity"])

        adjust_stock(
            product_id=product.id,
            store_id=product.store_id,
            quantity_change=Decimal("5.000"),
            reason="Restock",
        )

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("55.000")
        assert inventory.reserved_quantity == Decimal("10.000")

    def test_creates_inventory_for_positive_adjustment(
        self, product
    ):
        assert not Inventory.objects.filter(product=product).exists()

        created = adjust_stock(
            product_id=product.id,
            store_id=product.store_id,
            quantity_change=Decimal("25.000"),
            reason="Initial stock",
        )

        assert created.pk is not None
        assert created.available_quantity == Decimal("25.000")
        assert created.reserved_quantity == Decimal("0")

    def test_negative_adjustment_without_inventory_rejected(
        self, product
    ):
        with pytest.raises(ValidationError, match="no inventory record"):
            adjust_stock(
                product_id=product.id,
                store_id=product.store_id,
                quantity_change=Decimal("-5.000"),
                reason="Shrinkage",
            )

    def test_unknown_product_rejected(self, store, product):
        with pytest.raises(ValidationError, match="not found or inactive"):
            adjust_stock(
                product_id=999999,
                store_id=store.id,
                quantity_change=Decimal("5.000"),
                reason="Bad id",
            )

    def test_wrong_store_rejected(self, product, another_store):
        with pytest.raises(ValidationError, match="not found or inactive"):
            adjust_stock(
                product_id=product.id,
                store_id=another_store.id,
                quantity_change=Decimal("5.000"),
                reason="Cross-store",
            )

    def test_inactive_product_rejected(self, product, inventory):
        product.is_active = False
        product.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="not found or inactive"):
            adjust_stock(
                product_id=product.id,
                store_id=product.store_id,
                quantity_change=Decimal("5.000"),
                reason="Inactive",
            )

    def test_transaction_rollback_on_failure(
        self, product, inventory, monkeypatch
    ):
        def explode(self, **kwargs):
            raise RuntimeError("simulated db failure")

        monkeypatch.setattr(Inventory, "save", explode)

        with pytest.raises(RuntimeError, match="simulated db failure"):
            adjust_stock(
                product_id=product.id,
                store_id=product.store_id,
                quantity_change=Decimal("10.000"),
                reason="Rollback check",
            )

        inventory.refresh_from_db()
        assert inventory.available_quantity == Decimal("50.000")


@pytest.mark.django_db
class TestUpdateReorderLevel:

    def test_updates_reorder_level(self, product, inventory):
        updated = update_reorder_level(
            product_id=product.id,
            store_id=product.store_id,
            reorder_level=Decimal("12.500"),
        )

        assert updated.reorder_level == Decimal("12.500")

    def test_zero_reorder_level_allowed(self, product, inventory):
        updated = update_reorder_level(
            product_id=product.id,
            store_id=product.store_id,
            reorder_level=Decimal("0"),
        )

        assert updated.reorder_level == Decimal("0")

    def test_negative_reorder_level_rejected(self, product, inventory):
        with pytest.raises(ValidationError, match="non-negative"):
            update_reorder_level(
                product_id=product.id,
                store_id=product.store_id,
                reorder_level=Decimal("-1"),
            )

    def test_non_finite_reorder_level_rejected(
        self, product, inventory
    ):
        with pytest.raises(ValidationError, match="non-negative"):
            update_reorder_level(
                product_id=product.id,
                store_id=product.store_id,
                reorder_level=Decimal("NaN"),
            )

    def test_missing_inventory_rejected(self, product):
        with pytest.raises(ValidationError, match="inventory record"):
            update_reorder_level(
                product_id=product.id,
                store_id=product.store_id,
                reorder_level=Decimal("5"),
            )

    def test_inactive_product_rejected(self, product, inventory):
        product.is_active = False
        product.save(update_fields=["is_active"])

        with pytest.raises(ValidationError, match="not found or inactive"):
            update_reorder_level(
                product_id=product.id,
                store_id=product.store_id,
                reorder_level=Decimal("5"),
            )
