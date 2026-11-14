
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.stores.models import Store


def normalize_whatsapp_number(phone_number: str) -> str:
    """
    Normalize a WhatsApp sender identifier.

    Example:
        +91 98765 11111 -> 919876511111
        919876511111    -> 919876511111

    The incoming number must already include its country code.
    """

    if not isinstance(phone_number, str):
        raise ValidationError("Invalid WhatsApp number.")

    normalized = re.sub(r"\D", "", phone_number)

    if not normalized or not 8 <= len(normalized) <= 15:
        raise ValidationError("Invalid international phone number.")

    return normalized


@transaction.atomic
def get_or_create_customer(
    whatsapp_number: str,
    store_id: int,
    display_name: str = "",
):
    """
    Identify or create a customer and associate them with a store.

    Returns:
        CustomerProfile instance
    """

    phone = normalize_whatsapp_number(whatsapp_number)

    # STEP 1: Verify that the store exists and is active.
    store = Store.objects.get(
        id=store_id,
        is_active=True,
    )

    # STEP 2: Find an existing customer.
    profile = (
        CustomerProfile.objects
        .select_related("user")
        .filter(whatsapp_number=phone)
        .first()
    )

    # STEP 3: Create a new Django user and profile if necessary.
    if profile is None:
        User = get_user_model()

        username = f"wa_{phone}"

        user = User.objects.filter(username=username).first()

        if user is None:
            user = User.objects.create_user(
                username=username,
                password=None,
            )

        profile = CustomerProfile.objects.create(
            user=user,
            whatsapp_number=phone,
            display_name=display_name.strip(),
        )

    # STEP 4: Associate customer with the store.
    relationship, created = StoreCustomer.objects.get_or_create(
        store=store,
        customer=profile,
        defaults={"is_active": True},
    )

    # Reactivate an existing store relationship if necessary.
    if not relationship.is_active:
        relationship.is_active = True
        relationship.save(update_fields=["is_active"])

    # Update display name when a non-empty new name is provided.
    if display_name and profile.display_name != display_name.strip():
        profile.display_name = display_name.strip()
        profile.save(update_fields=["display_name", "updated_at"])

    return profile
