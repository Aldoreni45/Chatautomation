
import pytest

from apps.inventory.models import Inventory


@pytest.mark.django_db
class TestInventoryAPI:

    def test_inventory_list_returns_200(self, api_client):
        response = api_client.get("/api/inventory/")

        assert response.status_code == 200

    def test_inventory_can_filter_by_store(
        self, api_client, store
    ):
        response = api_client.get(
            "/api/inventory/",
            {"store_id": store.id},
        )

        assert response.status_code == 200

    def test_inventory_can_filter_by_product(
        self, api_client
    ):
        response = api_client.get(
            "/api/inventory/",
            {"product_id": 1},
        )

        assert response.status_code == 200
