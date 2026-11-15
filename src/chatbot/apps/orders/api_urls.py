from django.urls import path

from apps.orders.views import (
    CartSummaryAPIView,
    CartItemAPIView,
)

urlpatterns = [
    path(
        "",
        CartSummaryAPIView.as_view(),
        name="cart-summary",
    ),

    path(
        "items/",
        CartItemAPIView.as_view(),
        name="cart-items",
    ),
]