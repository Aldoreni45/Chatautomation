from django.contrib import admin

from .models import CustomerProfile, StoreCustomer


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "whatsapp_number",
        "display_name",
        "created_at",
    )

    search_fields = (
        "whatsapp_number",
        "display_name",
        "user__username",
    )


@admin.register(StoreCustomer)
class StoreCustomerAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "store",
        "customer",
        "is_active",
        "created_at",
    )

    list_filter = ("is_active", "store")

    search_fields = (
        "customer__whatsapp_number",
        "customer__display_name",
        "store__name",
    )