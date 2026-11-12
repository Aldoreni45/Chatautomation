
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.stores.models import Store
from apps.products.models import Category, Product, ProductAlias
from apps.inventory.models import Inventory
from apps.pricing.models import ProductPrice


PRODUCTS = [
    # Rice
    ("Rice", "Basmati Rice", "RICE001", "kg", 50, 120, ["basmati", "basmati rice", "premium rice"]),
    ("Rice", "Ponni Rice", "RICE002", "kg", 100, 65, ["ponni", "ponni arisi", "boiled rice"]),
    ("Rice", "Sona Masoori Rice", "RICE003", "kg", 40, 75, ["sona masoori", "sonamasuri"]),
    ("Rice", "Brown Rice", "RICE004", "kg", 0, 95, ["brown rice", "healthy rice"]),

    # Dairy
    ("Dairy", "Aavin Milk", "MILK001", "l", 20, 32, ["milk", "aavin paal", "aavin milk"]),
    ("Dairy", "Curd", "DAIRY001", "kg", 15, 80, ["yogurt", "thayir", "curd"]),
    ("Dairy", "Butter", "DAIRY002", "piece", 12, 55, ["butter"]),
    ("Dairy", "Paneer", "DAIRY003", "kg", 8, 320, ["paneer", "cottage cheese"]),

    # Staples
    ("Staples", "Sugar", "STAP001", "kg", 30, 48, ["sugar", "sakkarai"]),
    ("Staples", "Toor Dal", "STAP002", "kg", 25, 140, ["toor dal", "thuvaram paruppu"]),
    ("Staples", "Moong Dal", "STAP003", "kg", 18, 120, ["moong dal", "pasi paruppu"]),
    ("Staples", "Wheat Flour", "STAP004", "kg", 15, 55, ["atta", "wheat flour"]),
    ("Staples", "Salt", "STAP005", "kg", 40, 25, ["salt", "uppu"]),

    # Oils
    ("Oils", "Sunflower Oil", "OIL001", "l", 20, 150, ["sunflower oil", "cooking oil"]),
    ("Oils", "Groundnut Oil", "OIL002", "l", 10, 190, ["groundnut oil", "peanut oil", "kadalai ennai"]),

    # Snacks
    ("Snacks", "Marie Biscuits", "SNACK001", "packet", 25, 30, ["marie biscuit", "biscuits"]),
    ("Snacks", "Potato Chips", "SNACK002", "packet", 40, 20, ["chips", "potato chips"]),
    ("Snacks", "Almonds", "SNACK003", "kg", 5, 800, ["badam", "almonds"]),
    ("Snacks", "Cashews", "SNACK004", "kg", 0, 900, ["cashew", "mundhiri"]),

    # Beverages
    ("Beverages", "Coca-Cola", "BEV001", "piece", 30, 40, ["coke", "coca cola"]),
    ("Beverages", "Orange Juice", "BEV002", "l", 12, 110, ["orange juice", "juice"]),

    # Personal care
    ("Personal Care", "Bath Soap", "CARE001", "piece", 35, 35, ["soap", "bathing soap"]),
    ("Personal Care", "Shampoo", "CARE002", "piece", 20, 180, ["shampoo", "hair shampoo"]),
    ("Personal Care", "Toothpaste", "CARE003", "piece", 18, 95, ["toothpaste", "tooth paste"]),
    ("Personal Care", "Toothbrush", "CARE004", "piece", 22, 45, ["toothbrush", "brush"]),
]


class Command(BaseCommand):
    help = "Populate ShopMate with demo grocery inventory"

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            required=True,
            help="Existing Django owner username"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        try:
            owner = User.objects.get(username=options["owner"])
        except User.DoesNotExist:
            raise CommandError("Owner does not exist. Create a superuser first.")

        if not owner.is_active:
            raise CommandError("The selected owner account is inactive.")

        store, created = Store.objects.get_or_create(
            owner=owner,
            name="Aldo's Supermarket",
            defaults={
                "description": "Demo grocery store for ShopMate AI",
                "address": "Coimbatore, Tamil Nadu",
                "phone": "",
                "is_active": True,
            }
        )

        category_cache = {}
        created_products = 0

        for category_name, name, sku, unit, stock, price, aliases in PRODUCTS:

            category = category_cache.get(category_name)

            if category is None:
                category, _ = Category.objects.get_or_create(
                    store=store,
                    name=category_name,
                )
                category_cache[category_name] = category

            product, product_created = Product.objects.get_or_create(
                store=store,
                sku=sku,
                defaults={
                    "category": category,
                    "name": name,
                    "brand": "",
                    "description": f"{name} available at {store.name}",
                    "unit": unit,
                    "is_active": True,
                }
            )

            if product_created:
                created_products += 1

            Inventory.objects.get_or_create(
                product=product,
                defaults={
                    "available_quantity": Decimal(str(stock)),
                    "reserved_quantity": Decimal("0"),
                    "reorder_level": Decimal("5"),
                }
            )

            ProductPrice.objects.get_or_create(
                product=product,
                is_current=True,
                defaults={
                    "selling_price": Decimal(str(price)),
                    "currency": "INR",
                    "effective_from": timezone.now(),
                }
            )

            for alias in aliases:
                ProductAlias.objects.get_or_create(
                    product=product,
                    alias=alias,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(PRODUCTS)} products. "
                f"New products created: {created_products}. "
                f"Store: {store.name}"
            )
        )
