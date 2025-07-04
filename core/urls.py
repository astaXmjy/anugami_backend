from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Import viewsets from system_settings for multi-banners
from system_settings.views import BannerSectionViewSet, BannerItemViewSet

# API URL Patterns
api_v1_patterns = [
    # Authentication & Users
    path("auth/", include("system_users.urls", namespace="auth")),
    path("users/", include("system_users.urls", namespace="users")),
    # Product Management
    path("products/", include("products.urls", namespace="products")),
    path("categories/", include("categories.urls", namespace="categories")),
    path("brands/", include("products.urls", namespace="brands")),
    # Order Management
    path("orders/", include("orders.urls", namespace="orders")),
    path("payments/", include("payments.urls", namespace="payments")),
    path("shipping/", include("shipping_policies.urls", namespace="shipping")),
    # Seller Management
    path("sellers/", include("sellers.urls", namespace="sellers")),
    # Customer Features
    path("customers/", include("customers.urls", namespace="customers")),
    path("cart/", include("products.urls", namespace="cart")),
    path("wishlist/", include("products.urls", namespace="wishlist")),
    # Content Management
    path("media/", include("media_management.urls", namespace="media")),
    path('blogs/', include('blogs.urls', namespace='blogs')),
    path("faq/", include("faq.urls", namespace="faq")),
    # Marketing & Offers
    path("offers/", include("offers.urls", namespace="offers")),
    path("promo-codes/", include("promo_codes.urls", namespace="promo-codes")),
    # Analytics & Reports
    # path('analytics/', include('analytics.urls', namespace='analytics')),
    # path('reports/', include('reports.urls', namespace='reports')),
    # System settings
    path("system-settings/", include("system_settings.urls")),
    path("support-tickets/", include("support_tickets.urls")),
    path("chats/", include("chat.urls")),
    # Multi-banner routes (matched to frontend expected URLs)
    path(
        "multi-banners/sections/",
        BannerSectionViewSet.as_view({"get": "list", "post": "create"}),
        name="multi_banners_sections",
    ),
    path(
        "multi-banners/sections/<int:pk>/",
        BannerSectionViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="multi_banners_section_detail",
    ),
    path(
        "multi-banners/items/",
        BannerItemViewSet.as_view({"get": "list", "post": "create"}),
        name="multi_banners_items",
    ),
    path(
        "multi-banners/items/<int:pk>/",
        BannerItemViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="multi_banners_item_detail",
    ),
    path(
        "multi-banners/items/by-section/<int:section_id>/",
        BannerItemViewSet.as_view({"get": "by_section"}),
        name="multi_banners_items_by_section",
    ),
    path(
        "multi-banners/items/update-order/",
        BannerItemViewSet.as_view({"post": "update_order"}),
        name="multi_banners_update_order",
    ),
    # Contact Management
    path("contact/", include("contact.urls", namespace="contact")),
]


# Main URL Patterns
urlpatterns = [
    # Admin Panel
    path("admin/", admin.site.urls),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API Versions
    path("api/v1/", include((api_v1_patterns, "api_v1"), namespace="api_v1")),
    # Frontend Integration (optional, for Next.js or other frontend)
    # path('', include('core.web_urls')),
]

# Media and Static Files for Development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom Error Handlers
handler400 = "core.views.bad_request"
handler403 = "core.views.permission_denied"
handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"
