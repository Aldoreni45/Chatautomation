from django.db import models
from django.db.models import Q

from apps.products.models import Product


class ProductPrice(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="prices"
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    currency = models.CharField(
        max_length=3,
        default="INR"
    )

    is_current = models.BooleanField(default=True)

    effective_from = models.DateTimeField()

    effective_until = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_prices"

        constraints = [
            models.CheckConstraint(
                condition=Q(selling_price__gt=0),
                name="product_price_positive"
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(is_current=True),
                name="one_current_price_per_product"
            ),
        ]

        indexes = [
            models.Index(fields=["product", "is_current"]),
        ]

    def __str__(self):
        return f"{self.product.name}: {self.selling_price}"