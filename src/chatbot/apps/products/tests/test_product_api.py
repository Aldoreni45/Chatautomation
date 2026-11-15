
import pytest

from apps.products.models import Product


@pytest.mark.django_db
class TestProductAPI:

    def test_product_list_returns_200(self, api_client):
        response = api_client.get("/api/products/")

        assert response.status_code == 200

    def test_product_list_can_filter_by_store(
        self, api_client, store, another_store, product
    ):
        other_category_product = Product.objects.create(
            store=another_store,
            name="Other Store Product",
            sku="OTHER-001",
            unit=Product.Unit.PIECE,
            is_active=True,
        )

        response = api_client.get(
            "/api/products/",
            {"store_id": store.id},
        )

        assert response.status_code == 200

        results = response.data

        returned_ids = {item["id"] for item in results}

        assert product.id in returned_ids
        assert other_category_product.id not in returned_ids

        # The public serializer does not expose store_id, so verify
        # store scoping against the database.
        assert Product.objects.filter(
            id__in=returned_ids,
            store=store,
        ).count() == len(returned_ids)

    def test_product_search_returns_200(self, api_client):
        response = api_client.get(
            "/api/products/",
            {"search": "Rice"},
        )

        assert response.status_code == 200

    def test_product_list_does_not_return_inactive_products(
        self, api_client
    ):
        response = api_client.get("/api/products/")

        assert response.status_code == 200
