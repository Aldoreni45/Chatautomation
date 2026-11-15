from django.urls import path

from apps.products.management_api_views import (
    StoreProductListCreateAPIView,
    StoreProductDetailAPIView,
    StoreProductActivationAPIView,
)

urlpatterns = [
    path(
        "",
        StoreProductListCreateAPIView.as_view(),
        name="store-product-list-create",
    ),

    path(
        "<int:product_id>/",
        StoreProductDetailAPIView.as_view(),
        name="store-product-detail",
    ),

    path(
        "<int:product_id>/<str:action>/",
        StoreProductActivationAPIView.as_view(),
        name="store-product-activation",
    ),
]