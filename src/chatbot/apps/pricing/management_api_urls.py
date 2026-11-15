from django.urls import path

from apps.pricing.management_api_views import (
    StorePriceListAPIView,
    SetProductPriceAPIView,
    ProductPriceHistoryAPIView,
)

urlpatterns = [
    path(
        "",
        StorePriceListAPIView.as_view(),
        name="store-price-list",
    ),

    path(
        "<int:product_id>/",
        SetProductPriceAPIView.as_view(),
        name="set-product-price",
    ),

    path(
        "<int:product_id>/history/",
        ProductPriceHistoryAPIView.as_view(),
        name="product-price-history",
    ),
]