# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet
from .api_views import *
from .html_views import *

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
    # ShipMojo shipping endpoints
    # Core checkout endpoints
    path(
        "orders/checkout/",
        OrderViewSet.as_view({"post": "checkout"}),
        name="checkout",
    ),
    # Basic shipping management
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
        "orders/<int:pk>/check-serviceability/",
        OrderViewSet.as_view({"get": "check_serviceability"}),
        name="check-serviceability",
    ),
    path(
        "orders/<int:pk>/get-shipping-rates/",
        OrderViewSet.as_view({"get": "get_shipping_rates"}),
        name="get-shipping-rates",
    ),
    # Courier management
    path(
        "orders/<int:pk>/assign-courier/",
        OrderViewSet.as_view({"post": "assign_courier"}),
        name="assign-courier",
    ),
    path(
        "orders/<int:pk>/auto-assign-courier/",
        OrderViewSet.as_view({"post": "auto_assign_courier"}),
        name="auto-assign-courier",
    ),
    # Pickup management
    path(
        "orders/<int:pk>/schedule-pickup/",
        OrderViewSet.as_view({"post": "schedule_pickup"}),
        name="schedule-pickup",
    ),
    # Label and documentation
    path(
        "orders/<int:pk>/generate-label/",
        OrderViewSet.as_view({"post": "generate_label"}),
        name="generate-label",
    ),
    # Order cancellation
    path(
        "orders/<int:pk>/cancel-shipment/",
        OrderViewSet.as_view({"post": "cancel_shipment"}),
        name="cancel-shipment",
    ),
    # Warehouse management
    path(
        "orders/warehouses/",
        OrderViewSet.as_view({"get": "get_warehouses"}),
        name="get-warehouses",
    ),
    path(
        "orders/warehouses/create/",
        OrderViewSet.as_view({"post": "create_warehouse"}),
        name="create-warehouse",
    ),
    path(
        "orders/<int:pk>/update-warehouse/",
        OrderViewSet.as_view({"post": "update_warehouse"}),
        name="update-warehouse",
    ),
    # Return management
    path(
        "orders/return-reasons/",
        OrderViewSet.as_view({"get": "get_return_reasons"}),
        name="get-return-reasons",
    ),
    path(
        "orders/<int:pk>/create-return/",
        OrderViewSet.as_view({"post": "create_return_order"}),
        name="create-return-order",
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
        "orders/<int:pk>/request-invoice/",
        OrderViewSet.as_view({"post": "request_invoice"}),
        name="request-invoice",
    ),
    path(
        "orders/respond-to-invoice-request/",
        OrderViewSet.as_view({"post": "respond_to_invoice_request"}),
        name="respond-to-invoice-request",
    ),
    path(
        "all-products/",
        all_orders_products,
        name="all_orders_products",
    ),
    path(
        "by-seller/",
        orders_by_seller,
        name="orders_by_seller",
    ),
    path(
        "update-commission/",
        update_seller_commission,
        name="update_seller_commission",
    ),
    path(
        "see-commision-reports/",
        products_table_view,
        name="product-table-view",
    ),
]
