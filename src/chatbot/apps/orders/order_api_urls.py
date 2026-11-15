from django.urls import path

from apps.orders.order_api_views import (
    OrderConfirmAPIView,
    OrderHistoryAPIView,
    OrderDetailAPIView,
    OrderCancelAPIView,
    OrderCompleteAPIView,
)

urlpatterns = [
    path(
        "",
        OrderHistoryAPIView.as_view(),
        name="order-history",
    ),

    path(
        "confirm/",
        OrderConfirmAPIView.as_view(),
        name="order-confirm",
    ),

    path(
        "<int:order_id>/",
        OrderDetailAPIView.as_view(),
        name="order-detail",
    ),

    path(
        "<int:order_id>/cancel/",
        OrderCancelAPIView.as_view(),
        name="order-cancel",
    ),

    path(
        "<int:order_id>/complete/",
        OrderCompleteAPIView.as_view(),
        name="order-complete",
    ),
]