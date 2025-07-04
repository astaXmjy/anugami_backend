from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import ShippingPolicyViewSet, PublicShippingPolicyViewSet

app_name = "shipping_policies"

# Set up DRF router
router = DefaultRouter()
router.register(r"policies", ShippingPolicyViewSet, basename="shipping-policy")
router.register(
    r"public-policies", PublicShippingPolicyViewSet, basename="public-policy"
)

urlpatterns = [
    # DRF router URLs (recommended method)
    path("", include(router.urls)),
    # Legacy endpoints for backward compatibility
    path(
        "shipping-policies/",
        views.list_shipping_policies,
        name="list_shipping_policies",
    ),
    path(
        "shipping-policies/create/",
        views.create_shipping_policy,
        name="create_shipping_policy",
    ),
    path(
        "shipping-policies/<str:policy_id>/update/",
        views.update_shipping_policy,
        name="update_shipping_policy",
    ),
    path(
        "shipping-policies/<str:policy_id>/delete/",
        views.delete_shipping_policy,
        name="delete_shipping_policy",
    ),
]
