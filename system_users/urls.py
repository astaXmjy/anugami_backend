# system_users/urls.py
# Update your existing urls.py file with these routes

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    generate_qr,
    verify_otp_code,
    request_password_reset,
    reset_password,
    change_password,
    login,
    seller_login,
    # New ViewSets for role management
    SystemModuleViewSet,
    ModulePermissionViewSet,
    RoleViewSet,
)
from . import consumers

app_name = "system_users"

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
# Add the new routes
router.register(r"modules", SystemModuleViewSet, basename="system_module")
router.register(
    r"module-permissions", ModulePermissionViewSet, basename="module_permission"
)
router.register(r"roles", RoleViewSet, basename="role")

urlpatterns = [
    path("", include(router.urls)),
    path("login/", login, name="user_login"),
    path("seller/login/", seller_login, name="seller_login"),
    path("generate-qr/", generate_qr, name="generate_qr"),
    path("verify-otp/", verify_otp_code, name="verify_otp"),
    path(
        "request-password-reset/", request_password_reset, name="request_password_reset"
    ),
    path("reset-password/", reset_password, name="reset_password"),
    path("change-password/", change_password, name="change_password"),
    # WebSocket endpoint for user status
    path("ws/status/", consumers.UserStatusConsumer.as_asgi(), name="user_status_ws"),
]

# WebSocket URL patterns
websocket_urlpatterns = [
    path("system_users/ws/status/", consumers.UserStatusConsumer.as_asgi()),
]
