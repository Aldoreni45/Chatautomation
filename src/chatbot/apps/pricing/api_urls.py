from django.urls import path

from apps.pricing.views import (
    ProductPriceListAPIView,
    CalculateProductPriceAPIView,
)

urlpatterns = [
    path(
        "",
        ProductPriceListAPIView.as_view(),
        name="product-price-list",
    ),

    path(
        "calculate/",
        CalculateProductPriceAPIView.as_view(),
        name="calculate-product-price",
    ),
]