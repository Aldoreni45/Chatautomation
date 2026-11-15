from django.urls import path

from apps.stores.views import (
    StoreListCreateAPIView,
    StoreDetailAPIView,
    StoreDeactivateAPIView,
)

urlpatterns = [
    path(
        "",
        StoreListCreateAPIView.as_view(),
        name="store-list-create",
    ),

    path(
        "<int:pk>/",
        StoreDetailAPIView.as_view(),
        name="store-detail",
    ),

    path(
        "<int:store_id>/deactivate/",
        StoreDeactivateAPIView.as_view(),
        name="store-deactivate",
    ),
]
