
import pytest


@pytest.mark.django_db
class TestInventoryManagementAPI:

    def test_unauthenticated_user_cannot_access_inventory(
        self, api_client, store
    ):
        response = api_client.get(
            f"/api/stores/{store.id}/inventory/"
        )

        assert response.status_code in (401, 403)

    def test_owner_can_list_inventory(
        self, authenticated_client, store
    ):
        response = authenticated_client.get(
            f"/api/stores/{store.id}/inventory/"
        )

        assert response.status_code == 200

    def test_another_owner_cannot_access_inventory(
        self, another_authenticated_client, store
    ):
        response = another_authenticated_client.get(
            f"/api/stores/{store.id}/inventory/"
        )

        assert response.status_code in (403, 404)
