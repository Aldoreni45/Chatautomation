
import pytest

from apps.stores.models import Store


STORE_URL = "/api/stores/"


@pytest.mark.django_db
class TestStoreAPI:

    def test_owner_can_list_own_stores(
        self,
        authenticated_client,
        store,
    ):
        response = authenticated_client.get(STORE_URL)

        assert response.status_code == 200

        store_ids = [
            item["id"] for item in response.data
        ]

        assert store.id in store_ids

    def test_owner_can_create_store(
        self,
        authenticated_client,
        owner,
    ):
        payload = {
            "name": "New Supermarket",
            "description": "New test store",
            "address": "Coimbatore",
            "phone": "9876543212",
        }

        response = authenticated_client.post(
            STORE_URL,
            payload,
            format="json",
        )

        assert response.status_code == 201

        created_store = Store.objects.get(
            name="New Supermarket"
        )

        assert created_store.owner == owner

    def test_unauthenticated_user_cannot_create_store(
        self,
        api_client,
    ):
        payload = {
            "name": "Unauthorized Store",
        }

        response = api_client.post(
            STORE_URL,
            payload,
            format="json",
        )

        assert response.status_code in (401, 403)

        assert not Store.objects.filter(
            name="Unauthorized Store"
        ).exists()

    def test_owner_cannot_see_another_owners_store(
        self,
        authenticated_client,
        another_store,
    ):
        response = authenticated_client.get(STORE_URL)

        assert response.status_code == 200

        store_ids = [
            item["id"] for item in response.data
        ]

        assert another_store.id not in store_ids

    def test_owner_can_retrieve_own_store(
        self,
        authenticated_client,
        store,
    ):
        response = authenticated_client.get(
            f"{STORE_URL}{store.id}/"
        )

        assert response.status_code == 200
        assert response.data["id"] == store.id

    def test_owner_cannot_retrieve_another_owners_store(
        self,
        authenticated_client,
        another_store,
    ):
        response = authenticated_client.get(
            f"{STORE_URL}{another_store.id}/"
        )

        assert response.status_code in (403, 404)
