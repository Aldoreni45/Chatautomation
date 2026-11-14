from django.db import models
from django.conf import settings


class CustomerProfile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile"
    )

    whatsapp_number = models.CharField(
        max_length=20,
        unique=True
    )

    display_name = models.CharField(
        max_length=100,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "customer_profiles"

    def __str__(self):
        return self.display_name or self.whatsapp_number


from apps.stores.models import Store


class StoreCustomer(models.Model):

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="store_customers"
    )

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="store_relationships"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = "store_customers"

        constraints = [
            models.UniqueConstraint(
                fields=["store", "customer"],
                name="unique_customer_per_store"
            )
        ]

        indexes = [
            models.Index(fields=["store", "is_active"]),
            models.Index(fields=["customer", "is_active"]),
        ]

    def __str__(self):
        return f"{self.customer} - {self.store.name}"