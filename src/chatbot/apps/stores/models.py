from django.db import models
from django.conf import settings
# Create your models here.


class Store(models.Model):

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stores"
    )

    name = models.CharField(max_length=150)

    description = models.TextField(blank=True)

    address = models.TextField(blank=True)

    phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stores"
        indexes = [
            models.Index(fields=["owner", "is_active"]),
        ]

    def __str__(self):
        return self.name