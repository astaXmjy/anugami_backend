from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import AdminSellerViewSet

app_name = "sellers"

router = DefaultRouter()
router.register("sellers", views.SellerManagementViewSet, basename="seller")
router.register(
    "shipping-locations", views.ShippingLocationViewSet, basename="shipping-location"
)
router.register("orders", views.OrderViewSet, basename="order")
router.register("admin/sellers", AdminSellerViewSet, basename="admin-sellers")

urlpatterns = [
    path("", include(router.urls)),
    # Custom URLs for seller actions
    path(
        "sellers/register/",
        views.SellerManagementViewSet.as_view({"post": "register"}),
        name="seller-register",
    ),
    path(
        "sellers/request-email-otp/",
        views.SellerManagementViewSet.as_view({"post": "request_email_otp"}),
        name="request-email-otp",
    ),
    path(
        "sellers/verify-email-otp/",
        views.SellerManagementViewSet.as_view({"post": "verify_email_otp"}),
        name="verify-email-otp",
    ),
    path(
        "sellers/upload-pan-card/",
        views.SellerManagementViewSet.as_view({"post": "upload_pan_card"}),
        name="upload-pan-card",
    ),
    path(
        "sellers/account-settings/",
        views.SellerManagementViewSet.as_view({"get": "account_settings"}),
        name="account-settings",
    ),
    path(
        "sellers/update-bank-details/",
        views.SellerManagementViewSet.as_view({"put": "update_bank_details"}),
        name="update-bank-details",
    ),
]
