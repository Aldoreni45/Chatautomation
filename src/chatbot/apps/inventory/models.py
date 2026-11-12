from django.db import models
from django.db.models import F, Q

from apps.products.models import Product


class Inventory(models.Model):

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory"
    )

    available_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    reserved_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory"

        constraints = [
            models.CheckConstraint(
                condition=Q(available_quantity__gte=0),
                name="inventory_available_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(reserved_quantity__gte=0),
                name="inventory_reserved_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(reorder_level__gte=0),
                name="inventory_reorder_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(
                    reserved_quantity__lte=F("available_quantity")
                ),
                name="inventory_reserved_lte_available"
            ),
        ]

    @property
    def sellable_quantity(self):
        return self.available_quantity - self.reserved_quantity

    def __str__(self):
        return f"{self.product.name} inventory"