
from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework.test import APIClient

from apps.stores.models import Store
from apps.products.models import Category, Product, ProductAlias
from apps.inventory.models import Inventory
from apps.pricing.models import ProductPrice
from apps.customers.models import CustomerProfile, StoreCustomer
from apps.orders.models import Cart, CartItem, Order, OrderItem


User = get_user_model()


# --------------------------------------------------
# USERS
# --------------------------------------------------

@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="test_owner",
        email="owner@example.com",
        password="TestPassword123!",
    )


@pytest.fixture
def another_owner(db):
    return User.objects.create_user(
        username="another_owner",
        email="another@example.com",
        password="TestPassword123!",
    )


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        username="test_customer",
        password="TestPassword123!",
    )


# --------------------------------------------------
# STORES
# --------------------------------------------------

@pytest.fixture
def store(owner):
    return Store.objects.create(
        owner=owner,
        name="Test Supermarket",
        description="Test store",
        address="Coimbatore",
        phone="9876543210",
        is_active=True,
    )


@pytest.fixture
def another_store(another_owner):
    return Store.objects.create(
        owner=another_owner,
        name="Another Supermarket",
        description="Another test store",
        address="Coimbatore",
        phone="9876543211",
        is_active=True,
    )


# --------------------------------------------------
# CUSTOMERS
# --------------------------------------------------

@pytest.fixture
def customer_profile(customer):
    return CustomerProfile.objects.create(
        user=customer,
        whatsapp_number="919876543210",
        display_name="Test Customer",
    )


@pytest.fixture
def store_customer(store, customer_profile):
    return StoreCustomer.objects.create(
        store=store,
        customer=customer_profile,
        is_active=True,
    )


# --------------------------------------------------
# PRODUCTS
# --------------------------------------------------

@pytest.fixture
def category(store):
    return Category.objects.create(
        store=store,
        name="Groceries",
        description="Test grocery category",
    )


@pytest.fixture
def product(store, category):
    return Product.objects.create(
        store=store,
        category=category,
        name="Basmati Rice",
        brand="Test Brand",
        sku="RICE-001",
        description="Premium basmati rice",
        unit=Product.Unit.KG,
        is_active=True,
    )


# --------------------------------------------------
# INVENTORY
# --------------------------------------------------

@pytest.fixture
def inventory(product):
    return Inventory.objects.create(
        product=product,
        available_quantity=Decimal("50.000"),
        reserved_quantity=Decimal("0.000"),
        reorder_level=Decimal("5.000"),
    )


# --------------------------------------------------
# PRICING
# --------------------------------------------------

@pytest.fixture
def product_price(product):
    return ProductPrice.objects.create(
        product=product,
        selling_price=Decimal("120.00"),
        currency="INR",
        is_current=True,
        effective_from=timezone.now(),
        effective_until=None,
    )


@pytest.fixture
def product_alias(product):
    return ProductAlias.objects.create(
        product=product,
        alias="Basmati Rice 5kg",
    )


# --------------------------------------------------
# CARTS AND ORDERS
# --------------------------------------------------

@pytest.fixture
def cart(customer, store):
    return Cart.objects.create(
        customer=customer,
        store=store,
        status=Cart.Status.ACTIVE,
    )


@pytest.fixture
def cart_item(cart, product):
    return CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=Decimal("2.000"),
    )


@pytest.fixture
def order(customer, store):
    return Order.objects.create(
        customer=customer,
        store=store,
        status=Order.Status.CONFIRMED,
        subtotal=Decimal("240.00"),
        currency="INR",
    )


@pytest.fixture
def order_item(order, product):
    return OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        sku=product.sku,
        unit=product.unit,
        quantity=Decimal("2.000"),
        unit_price=Decimal("120.00"),
        line_total=Decimal("240.00"),
    )


# --------------------------------------------------
# API CLIENTS
# --------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, owner):
    api_client.force_authenticate(user=owner)
    return api_client


@pytest.fixture
def customer_client(customer):
    client = APIClient()
    client.force_authenticate(user=customer)
    return client


@pytest.fixture
def another_authenticated_client(another_owner):
    client = APIClient()
    client.force_authenticate(user=another_owner)
    return client
