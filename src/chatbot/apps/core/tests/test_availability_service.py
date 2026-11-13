
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.stores.models import Store
from apps.products.models import Product, ProductAlias
from apps.inventory.models import Inventory
from apps.pricing.models import ProductPrice
from apps.core.services.availability_service import (
    check_product_availability,
)


class AvailabilityServiceTests(TestCase):

    def setUp(self):
        """
        Create isolated test data.

        Django creates a separate test database, so these
        records will not modify your actual Supabase data.
        """

        User = get_user_model()

        self.owner = User.objects.create_user(
            username="test_owner",
            password="test_password",
        )

        self.store = Store.objects.create(
            owner=self.owner,
            name="Test Supermarket",
            description="Test store",
            address="Coimbatore",
            is_active=True,
        )

        self.basmati = self.create_product(
            name="Basmati Rice",
            sku="TEST001",
            unit="kg",
            stock="50",
            price="120.00",
            aliases=["basmati", "premium rice"],
        )

        self.almonds = self.create_product(
            name="Almonds",
            sku="TEST002",
            unit="kg",
            stock="5",
            price="800.00",
            aliases=["badam", "almonds"],
        )

        self.brown_rice = self.create_product(
            name="Brown Rice",
            sku="TEST003",
            unit="kg",
            stock="0",
            price="95.00",
            aliases=["brown rice"],
        )

        self.ponni_rice = self.create_product(
            name="Ponni Rice",
            sku="TEST004",
            unit="kg",
            stock="30",
            price="65.00",
            aliases=["ponni", "ponni arisi"],
        )

        self.aavin_milk = self.create_product(
            name="Aavin Milk",
            sku="TEST005",
            unit="l",
            stock="20",
            price="32.00",
            aliases=["milk", "aavin paal"],
        )

    def create_product(
        self,
        name,
        sku,
        unit,
        stock,
        price=None,
        aliases=None,
    ):
        """Helper to create a product and its related records."""

        product = Product.objects.create(
            store=self.store,
            name=name,
            sku=sku,
            unit=unit,
            is_active=True,
        )

        Inventory.objects.create(
            product=product,
            available_quantity=Decimal(stock),
            reserved_quantity=Decimal("0"),
            reorder_level=Decimal("5"),
        )

        if price is not None:
            ProductPrice.objects.create(
                product=product,
                selling_price=Decimal(price),
                currency="INR",
                is_current=True,
                effective_from=timezone.now(),
            )

        for alias in aliases or []:
            ProductAlias.objects.create(
                product=product,
                alias=alias,
            )

        return product

    def test_exact_alias_matching(self):
        result = check_product_availability(
            self.store.id,
            "basmati",
            Decimal("2"),
        )

        self.assertEqual(result.status, "available")
        self.assertEqual(result.product, self.basmati)

    def test_tamil_alias_matching(self):
        result = check_product_availability(
            self.store.id,
            "aavin paal",
            Decimal("1"),
        )

        self.assertEqual(result.status, "available")
        self.assertEqual(result.product, self.aavin_milk)

    def test_ambiguous_product_matching(self):
        result = check_product_availability(
            self.store.id,
            "rice",
            Decimal("2"),
        )

        self.assertEqual(result.status, "ambiguous")
        self.assertGreater(len(result.matches), 1)

    def test_unknown_product(self):
        result = check_product_availability(
            self.store.id,
            "pizza",
            Decimal("2"),
        )

        self.assertEqual(result.status, "not_found")

    def test_sufficient_stock(self):
        result = check_product_availability(
            self.store.id,
            "basmati",
            Decimal("2"),
        )

        self.assertEqual(result.status, "available")
        self.assertEqual(
            result.inventory.fulfillable_quantity,
            Decimal("2"),
        )
        self.assertEqual(
            result.pricing.subtotal,
            Decimal("240.00"),
        )

    def test_partial_stock(self):
        result = check_product_availability(
            self.store.id,
            "almonds",
            Decimal("10"),
        )

        self.assertEqual(result.status, "partially_available")
        self.assertEqual(
            result.inventory.fulfillable_quantity,
            Decimal("5"),
        )
        self.assertEqual(
            result.inventory.shortage_quantity,
            Decimal("5"),
        )
        self.assertEqual(
            result.pricing.subtotal,
            Decimal("4000.00"),
        )

    def test_zero_stock(self):
        result = check_product_availability(
            self.store.id,
            "brown rice",
            Decimal("2"),
        )

        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.pricing)

    def test_invalid_quantity(self):
        result = check_product_availability(
            self.store.id,
            "basmati",
            Decimal("-2"),
        )

        self.assertEqual(result.status, "invalid_quantity")

    def test_missing_price(self):
        product = self.create_product(
            name="Test Product",
            sku="TEST006",
            unit="kg",
            stock="10",
            price=None,
            aliases=["test item"],
        )

        result = check_product_availability(
            self.store.id,
            "test item",
            Decimal("2"),
        )

        self.assertEqual(result.status, "price_unavailable")
        self.assertEqual(result.product, product)
        self.assertIsNotNone(result.inventory)
        self.assertIsNotNone(result.pricing)
