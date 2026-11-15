
import pytest


@pytest.mark.django_db
class TestPricingAPI:

    def test_price_list_returns_200(self, api_client):
        response = api_client.get("/api/pricing/")

        assert response.status_code == 200

    def test_price_list_can_filter_by_product(
        self, api_client
    ):
        response = api_client.get(
            "/api/pricing/",
            {"product_id": 1},
        )

        assert response.status_code == 200
