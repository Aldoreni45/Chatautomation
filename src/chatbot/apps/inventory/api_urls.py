from django.urls import path

from apps.inventory.views import (
    InventoryListAPIView,
    InventoryDetailAPIView,
)

urlpatterns = [
    path(
        "",
        InventoryListAPIView.as_view(),
        name="inventory-list",
    ),

    path(
        "<int:product_id>/",
        InventoryDetailAPIView.as_view(),
        name="inventory-detail",
    ),
]