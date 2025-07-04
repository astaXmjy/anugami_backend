# admin.py
from django.contrib import admin
from .models import (
    Order,
    OrderItem,
    OrderAddress,
    ShippingDetails,
    ShipmentStatusUpdate,
    PaymentDetails,
    RefundDetails,
    InvoiceRequest
)

# Register your models here.


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "seller",
        "status",
        "total_amount",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("order_number", "user__username", "seller__name")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_id", "name", "quantity", "final_price", "status")
    list_filter = ("status",)
    search_fields = ("order__order_number", "name", "product_id")
    raw_id_fields = ("order",)


@admin.register(OrderAddress)
class OrderAddressAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "address_type",
        "full_name",
        "city",
        "state",
        "country",
        "pincode",
    )
    list_filter = ("address_type", "city", "state", "country")
    search_fields = ("order__order_number", "full_name", "city", "state")
    raw_id_fields = ("order",)


@admin.register(ShippingDetails)
class ShippingDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "provider",
        "tracking_id",
        "courier_name",
        "status",
        "expected_delivery",
    )
    list_filter = ("provider", "status", "expected_delivery")
    search_fields = ("order__order_number", "tracking_id", "courier_name")
    raw_id_fields = ("order",)
    readonly_fields = ("shiprocket_response",)


@admin.register(ShipmentStatusUpdate)
class ShipmentStatusUpdateAdmin(admin.ModelAdmin):
    list_display = ("shipping", "status", "status_date", "location", "activity")
    list_filter = ("status", "status_date")
    search_fields = ("shipping__order__order_number", "status", "location")
    raw_id_fields = ("shipping",)
    readonly_fields = ("status_date",)


@admin.register(PaymentDetails)
class PaymentDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "method",
        "payment_status",
        "amount_paid",
        "transaction_id",
    )
    list_filter = ("method", "payment_status")
    search_fields = ("order__order_number", "transaction_id")
    raw_id_fields = ("order",)
    readonly_fields = ("phonepe_response",)


@admin.register(RefundDetails)
class RefundDetailsAdmin(admin.ModelAdmin):
    list_display = ("payment", "refund_id", "refund_amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("payment__order__order_number", "refund_id")
    raw_id_fields = ("payment",)
    readonly_fields = ("created_at", "updated_at")

# Add this to your admin.py file

@admin.register(InvoiceRequest)
class InvoiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "requested_by",
        "status",
        "requested_at",
        "processed_at",
    )
    list_filter = ("status", "requested_at", "processed_at")
    search_fields = ("order__order_number", "requested_by__username", "notes")
    readonly_fields = ("requested_at",)
    date_hierarchy = "requested_at"
    fields = (
        "order",
        "requested_by",
        "notes",
        "status",
        "seller_notes",
        "processed_at",
        "invoice_file",
    )