
import pytest

from apps.products.models import Product


@pytest.mark.django_db
class TestProductManagementAPI:

    def test_unauthenticated_user_cannot_list_products(
        self, api_client, store
    ):
        response = api_client.get(
            f"/api/stores/{store.id}/products/"
        )

        assert response.status_code in (401, 403)

    def test_owner_can_list_products(
        self, authenticated_client, store
    ):
        response = authenticated_client.get(
            f"/api/stores/{store.id}/products/"
        )

        assert response.status_code == 200

    def test_another_owner_cannot_access_store_products(
        self, another_authenticated_client, store
    ):
        response = another_authenticated_client.get(
            f"/api/stores/{store.id}/products/"
        )

        assert response.status_code in (403, 404)
