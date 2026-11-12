from django.db import models
from apps.stores.models import Store


class Category(models.Model):

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    class Meta:
        db_table = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "name"],
                name="unique_category_per_store"
            )
        ]

    def __str__(self):
        return self.name


class Product(models.Model):

    class Unit(models.TextChoices):
        KG = "kg", "Kilogram"
        GRAM = "g", "Gram"
        LITRE = "l", "Litre"
        ML = "ml", "Millilitre"
        PIECE = "piece", "Piece"
        PACKET = "packet", "Packet"
        BOX = "box", "Box"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="products"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products"
    )

    name = models.CharField(max_length=200)

    brand = models.CharField(max_length=100, blank=True)

    sku = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    unit = models.CharField(
        max_length=20,
        choices=Unit.choices
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"

        constraints = [
            models.UniqueConstraint(
                fields=["store", "sku"],
                name="unique_product_sku_per_store"
            )
        ]

        indexes = [
            models.Index(fields=["store", "name"]),
            models.Index(fields=["store", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.store.name}"

class ProductAlias(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="aliases"
    )

    alias = models.CharField(max_length=200)

    class Meta:
        db_table = "product_aliases"

        constraints = [
            models.UniqueConstraint(
                fields=["product", "alias"],
                name="unique_product_alias"
            )
        ]

    def __str__(self):
        return self.alias