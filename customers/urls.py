# customers/urls.py - Updated with both PUT and DELETE methods for cart items

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet

app_name = "customers"

router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")

urlpatterns = [
    path("", include(router.urls)),
    # Authentication Endpoints
    path(
        "auth/",
        include(
            [
                path(
                    "register/",
                    CustomerViewSet.as_view({"post": "register"}),
                    name="register",
                ),
                path(
                    "verify-email/",
                    CustomerViewSet.as_view({"post": "verify_email"}),
                    name="verify-email",
                ),
                path(
                    "login/", CustomerViewSet.as_view({"post": "login"}), name="login"
                ),
                path(
                    "logout/",
                    CustomerViewSet.as_view({"post": "logout"}),
                    name="logout",
                ),
                path(
                    "reset-password/",
                    CustomerViewSet.as_view({"post": "reset_password"}),
                    name="reset-password",
                ),
            ]
        ),
    ),
    # Profile Management
    path(
        "profile/",
        include(
            [
                path("", CustomerViewSet.as_view({"get": "profile"}), name="profile"),
                path(
                    "update/",
                    CustomerViewSet.as_view({"put": "update_profile"}),
                    name="update-profile",
                ),
                path(
                    "delete/",
                    CustomerViewSet.as_view({"delete": "delete_profile"}),
                    name="delete-profile",
                ),
            ]
        ),
    ),
    # Address Management
    path(
        "addresses/",
        include(
            [
                path(
                    "",
                    CustomerViewSet.as_view({"get": "addresses"}),
                    name="list-addresses",
                ),
                path(
                    "add/",
                    CustomerViewSet.as_view({"post": "add_address"}),
                    name="add-address",
                ),
                path(
                    "<str:pk>/update/",
                    CustomerViewSet.as_view({"put": "update_address"}),
                    name="update-address",
                ),
                path(
                    "<str:pk>/delete/",
                    CustomerViewSet.as_view({"delete": "delete_address"}),
                    name="delete-address",
                ),
            ]
        ),
    ),
    # Cart Management - With both PUT and DELETE methods
    path(
        "cart/",
        include(
            [
                path("", CustomerViewSet.as_view({"get": "cart"}), name="view-cart"),
                path(
                    "add/",
                    CustomerViewSet.as_view({"post": "add_to_cart"}),
                    name="add-to-cart",
                ),
                path(
                    "remove/",
                    CustomerViewSet.as_view({"post": "remove_from_cart"}),
                    name="remove-from-cart",
                ),
                path(
                    "update/",
                    CustomerViewSet.as_view({"post": "update_cart"}),
                    name="update-cart",
                ),
                path(
                    "clear/",
                    CustomerViewSet.as_view({"post": "clear_cart"}),
                    name="clear-cart",
                ),
                path(
                    "summary/",
                    CustomerViewSet.as_view({"get": "cart_summary"}),
                    name="cart-summary",
                ),
                path(
                    'merge-carts/', CustomerViewSet.as_view({'post':'merge_carts'}), name ='merge-carts'
                ),
                path(
                    "sync-prices/",
                    CustomerViewSet.as_view({"post": "sync_cart_prices"}),
                    name="sync-cart-prices",
                ),
                # Updated with both PUT and DELETE methods
                path(
                    "item/<str:pk>/",
                    CustomerViewSet.as_view(
                        {"put": "update_cart_item", "delete": "remove_cart_item"}
                    ),
                    name="cart-item",
                ),
            ]
        ),
    ),
    # Wishlist Management
    path(
        "wishlist/",
        include(
            [
                path(
                    "add/",
                    CustomerViewSet.as_view({"post": "add_to_wishlist"}),
                    name="add-to-wishlist",
                ),
                path(
                    "remove/",
                    CustomerViewSet.as_view({"post": "remove_from_wishlist"}),
                    name="remove-from-wishlist",
                ),
            ]
        ),
    ),
    # Wallet & Transactions
    path(
        "wallet/",
        include(
            [
                path(
                    "update/",
                    CustomerViewSet.as_view({"post": "update_wallet"}),
                    name="update-wallet",
                ),
                path(
                    "transactions/",
                    CustomerViewSet.as_view({"get": "transactions"}),
                    name="wallet-transactions",
                ),
            ]
        ),
    ),
    # Order Statistics
    path(
        "order-stats/",
        CustomerViewSet.as_view({"get": "order_stats"}),
        name="order-stats",
    ),
    # Activity & Interactions
    path(
        "activity/",
        include(
            [
                path(
                    "record/",
                    CustomerViewSet.as_view({"post": "record_activity"}),
                    name="record-activity",
                ),
                path(
                    "interactions/",
                    CustomerViewSet.as_view({"get": "get_interactions"}),
                    name="get-interactions",
                ),
            ]
        ),
    ),
    # Update the wishlist section in urls.py to include anonymous access

# Wishlist Management
path(
    "wishlist/",
    include(
        [
            path(
                "", CustomerViewSet.as_view({"get": "wishlist"}), name="view-wishlist"
            ),
            path(
                "add/",
                CustomerViewSet.as_view({"post": "add_to_wishlist"}),
                name="add-to-wishlist",
            ),
            path(
                "remove/",
                CustomerViewSet.as_view({"post": "remove_from_wishlist"}),
                name="remove-from-wishlist",
            ),
            path(
                "clear/",
                CustomerViewSet.as_view({"post": "clear_wishlist"}),
                name="clear-wishlist",
            ),
            path(
                "count/",
                CustomerViewSet.as_view({"get": "wishlist_count"}),
                name="wishlist-count",
            ),
            path(
                "check/",
                CustomerViewSet.as_view({"post": "is_in_wishlist"}),
                name="is-in-wishlist",
            ),
            path(
                "merge/", 
                CustomerViewSet.as_view({"post": "merge_wishlists"}), 
                name="merge-wishlists"
            ),
            path(
                "item/<str:pk>/",
                CustomerViewSet.as_view({"delete": "remove_wishlist_item"}),
                name="wishlist-item",
            ),
        ]
    ),
),
path('contact-us/', CustomerViewSet.as_view({'post': 'contact_us'}), name='contact-us')
]
