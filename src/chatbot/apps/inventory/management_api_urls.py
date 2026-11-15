from django.urls import path

from apps.inventory.management_api_views import (
    StoreInventoryListAPIView,
    StockAdjustmentAPIView,
    ReorderLevelAPIView,
)

urlpatterns = [
    path(
        "",
        StoreInventoryListAPIView.as_view(),
        name="store-inventory-list",
    ),

    path(
        "<int:product_id>/adjust/",
        StockAdjustmentAPIView.as_view(),
        name="stock-adjustment",
    ),

    path(
        "<int:product_id>/reorder-level/",
        ReorderLevelAPIView.as_view(),
        name="reorder-level-update",
    ),
]