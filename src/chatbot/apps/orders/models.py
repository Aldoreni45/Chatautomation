
from django.conf import settings
from django.db import models
from django.db.models import Q
import uuid


class Cart(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONVERTED = "converted", "Converted"
        ABANDONED = "abandoned", "Abandoned"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="carts",
    )

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="carts",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "carts"

        constraints = [
            models.UniqueConstraint(
                fields=["customer", "store"],
                condition=Q(status="active"),
                name="one_active_cart_per_customer_store",
            ),
        ]

        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["store", "status"]),
        ]

    def __str__(self):
        return f"Cart {self.id} - {self.customer}"



class CartItem(models.Model):

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="cart_items",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart_items"

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_product_per_cart",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="cart_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Order(models.Model):

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    order_number = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="INR",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"

        indexes = [
            models.Index(fields=["customer", "created_at"]),
            models.Index(fields=["store", "status"]),
        ]

    def __str__(self):
        return str(self.order_number)


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    # Historical snapshots
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        db_table = "order_items"

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gt=0),
                name="order_item_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=0),
                name="order_item_total_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

