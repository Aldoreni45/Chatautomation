
import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.customers.models import CustomerProfile, StoreCustomer
from apps.customers.services.customer_service import (
    get_or_create_customer,
    normalize_whatsapp_number,
)
from apps.stores.models import Store


User = get_user_model()


@pytest.mark.django_db
class TestNormalizeWhatsappNumber:

    def test_strips_formatting_characters(self):
        assert normalize_whatsapp_number(
            "+91 98765-43210"
        ) == "919876543210"

    def test_passes_through_digits(self):
        assert normalize_whatsapp_number(
            "919876543210"
        ) == "919876543210"

    def test_rejects_non_string_input(self):
        with pytest.raises(ValidationError):
            normalize_whatsapp_number(None)

        with pytest.raises(ValidationError):
            normalize_whatsapp_number(919876543210)

    def test_rejects_too_short_number(self):
        with pytest.raises(ValidationError):
            normalize_whatsapp_number("12345")

    def test_rejects_empty_number(self):
        with pytest.raises(ValidationError):
            normalize_whatsapp_number("")

        with pytest.raises(ValidationError):
            normalize_whatsapp_number("+++---")

    def test_rejects_too_long_number(self):
        with pytest.raises(ValidationError):
            normalize_whatsapp_number("1234567890123456")


@pytest.mark.django_db
class TestGetOrCreateCustomer:

    def test_creates_customer_profile_and_relationship(self, store):
        profile = get_or_create_customer(
            whatsapp_number="+91 98765 11111",
            store_id=store.id,
            display_name="New Customer",
        )

        assert profile.whatsapp_number == "919876511111"
        assert profile.display_name == "New Customer"

        relationship = StoreCustomer.objects.get(
            store=store,
            customer=profile,
        )
        assert relationship.is_active is True

    def test_creates_user_with_unusable_password(self, store):
        profile = get_or_create_customer(
            whatsapp_number="919876522222",
            store_id=store.id,
        )

        user = profile.user
        assert user.username == "wa_919876522222"
        assert user.has_usable_password() is False

    def test_reuses_existing_customer(self, store, customer_profile):
        profile = get_or_create_customer(
            whatsapp_number="919876543210",
            store_id=store.id,
        )

        assert profile.id == customer_profile.id
        assert CustomerProfile.objects.count() == 1

    def test_is_idempotent_for_same_store(self, store):
        first = get_or_create_customer(
            whatsapp_number="919876533333",
            store_id=store.id,
        )
        second = get_or_create_customer(
            whatsapp_number="919876533333",
            store_id=store.id,
        )

        assert first.id == second.id
        assert StoreCustomer.objects.filter(
            store=store,
            customer=first,
        ).count() == 1

    def test_reactivates_inactive_relationship(self, store, store_customer):
        store_customer.is_active = False
        store_customer.save(update_fields=["is_active"])

        profile = get_or_create_customer(
            whatsapp_number="919876543210",
            store_id=store.id,
        )

        store_customer.refresh_from_db()
        assert store_customer.is_active is True
        assert profile.id == store_customer.customer_id

    def test_updates_display_name_when_provided(
        self, store, customer_profile
    ):
        profile = get_or_create_customer(
            whatsapp_number="919876543210",
            store_id=store.id,
            display_name="Updated Name",
        )

        assert profile.display_name == "Updated Name"

    def test_keeps_display_name_when_empty(
        self, store, customer_profile
    ):
        get_or_create_customer(
            whatsapp_number="919876543210",
            store_id=store.id,
            display_name="",
        )

        customer_profile.refresh_from_db()
        assert customer_profile.display_name == "Test Customer"

    def test_same_number_gets_separate_relationship_per_store(
        self, store, another_store
    ):
        profile = get_or_create_customer(
            whatsapp_number="919876544444",
            store_id=store.id,
        )
        same_profile = get_or_create_customer(
            whatsapp_number="919876544444",
            store_id=another_store.id,
        )

        assert same_profile.id == profile.id
        assert StoreCustomer.objects.filter(
            customer=profile,
        ).count() == 2

    def test_rejects_invalid_number(self, store):
        with pytest.raises(ValidationError):
            get_or_create_customer(
                whatsapp_number="not-a-number",
                store_id=store.id,
            )

        assert CustomerProfile.objects.count() == 0
        assert StoreCustomer.objects.count() == 0

    def test_rejects_inactive_store(self, owner, store):
        store.is_active = False
        store.save(update_fields=["is_active"])

        with pytest.raises(Store.DoesNotExist):
            get_or_create_customer(
                whatsapp_number="919876555555",
                store_id=store.id,
            )

    def test_rejects_nonexistent_store(self, store):
        with pytest.raises(Store.DoesNotExist):
            get_or_create_customer(
                whatsapp_number="919876555555",
                store_id=999999,
            )

    def test_same_number_different_formatting_reuses_profile(
        self, store
    ):
        first = get_or_create_customer(
            whatsapp_number="+91 98765 43210",
            store_id=store.id,
        )
        second = get_or_create_customer(
            whatsapp_number="919876543210",
            store_id=store.id,
        )

        assert first.id == second.id
        assert CustomerProfile.objects.count() == 1

    def test_display_name_is_stripped(self, store):
        profile = get_or_create_customer(
            whatsapp_number="919876566666",
            store_id=store.id,
            display_name="   Padded Name   ",
        )

        assert profile.display_name == "Padded Name"
