# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet

app_name = "orders"

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")

urlpatterns = [
    path("", include(router.urls)),
    # Payment endpoints
    path(
        "orders/<int:pk>/initiate-payment/",
        OrderViewSet.as_view({"post": "initiate_payment"}),
        name="initiate-payment",
    ),
    path(
        "orders/<int:pk>/check-payment/",
        OrderViewSet.as_view({"get": "check_payment_status"}),
        name="check-payment-status",
    ),
    path(
        "orders/<int:pk>/refund/",
        OrderViewSet.as_view({"post": "refund_payment"}),
        name="refund-payment",
    ),
    path(
        "orders/<int:pk>/check-refund/",
        OrderViewSet.as_view({"get": "check_refund_status"}),
        name="check-refund-status",
    ),
    # Shipping endpoints
    path(
        "orders/checkout/",
        OrderViewSet.as_view({"post": "checkout"}),
        name="checkout",
    ),
    path(
        "orders/<int:pk>/create-shipment/",
        OrderViewSet.as_view({"post": "create_shipment"}),
        name="create-shipment",
    ),
    path(
        "orders/<int:pk>/track/",
        OrderViewSet.as_view({"get": "track"}),
        name="track-order",
    ),
    path(
        "orders/<int:pk>/generate-label/",
        OrderViewSet.as_view({"post": "generate_label"}),
        name="generate-label",
    ),
    path(
        "orders/<int:pk>/generate-manifest/",
        OrderViewSet.as_view({"post": "generate_manifest"}),
        name="generate-manifest",
    ),
    path(
        "orders/<int:pk>/request-pickup/",
        OrderViewSet.as_view({"post": "request_pickup"}),
        name="request-pickup",
    ),
    path(
        "orders/<int:pk>/cancel-shipment/",
        OrderViewSet.as_view({"post": "cancel_shipment"}),
        name="cancel-shipment",
    ),
    path(
        "orders/<int:pk>/check-serviceability/",
        OrderViewSet.as_view({"get": "check_serviceability"}),
        name="check-serviceability",
    ),
    path(
        "orders/<int:pk>/mark-shipped/",
        OrderViewSet.as_view({"post": "mark_as_shipped"}),
        name="mark-as-shipped",
    ),
    path(
        "orders/<int:pk>/mark-delivered/",
        OrderViewSet.as_view({"post": "mark_as_delivered"}),
        name="mark-as-delivered",
    ),
    # Utility endpoints
    path(
        "pickup-locations/",
        OrderViewSet.as_view({"get": "get_pickup_locations"}),
        name="pickup-locations",
    ),
    path(
        "orders/<int:pk>/download-invoice/",
        OrderViewSet.as_view({"get": "download_invoice"}),
        name="download-invoice",
    ),
    # Webhook endpoints
    path(
        "webhooks/phonepe/",
        OrderViewSet.as_view({"post": "phonepe_callback"}),
        name="phonepe-webhook",
    ),
    path(
        "webhooks/shiprocket/",
        OrderViewSet.as_view({"post": "shiprocket_webhook"}),
        name="shiprocket-webhook",
    ),
    path(
        "orders/<int:pk>/request-invoice/",
        OrderViewSet.as_view({"post": "request_invoice"}),
        name="request-invoice",
    ),
    path(
        "orders/respond-to-invoice-request/",
        OrderViewSet.as_view({"post": "respond_to_invoice_request"}),
        name="respond-to-invoice-request",
    ),
]
