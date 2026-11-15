"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        "api/products/",
        include("apps.products.api_urls"),
    ),
    path(
        "api/inventory/",
        include("apps.inventory.api_urls"),
    ),
    path(
        "api/pricing/",
        include("apps.pricing.api_urls"),
    ),
    path(
    "api/cart/",
    include("apps.orders.api_urls"),
),
    path("api/orders/", include("apps.orders.order_api_urls")),
    path(
    "api/auth/",
    include("apps.core.api_urls"),
),
path(
    "api/stores/",
    include("apps.stores.api_urls"),
),
path(
    "api/stores/<int:store_id>/products/",
    include("apps.products.management_api_urls"),
),
path(
    "api/stores/<int:store_id>/inventory/",
    include("apps.inventory.management_api_urls"),
),
path(
    "api/stores/<int:store_id>/prices/",
    include("apps.pricing.management_api_urls"),
),
]
