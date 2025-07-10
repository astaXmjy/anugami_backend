# orders/admin.py - Updated for Shipmojo integration

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.http import urlencode
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
        "shipping_status",
        "view_shipping_details",
    )
    list_filter = ("status", "created_at", "updated_at", "seller")
    search_fields = ("order_number", "user__username", "seller__business_name")
    readonly_fields = ("created_at", "updated_at", "order_number")
    date_hierarchy = "created_at"
    raw_id_fields = ("user", "seller")
    
    fieldsets = (
        ("Order Information", {
            "fields": (
                "order_number", "user", "seller", "status", 
                "total_amount", "created_at", "updated_at"
            )
        }),
        ("Additional Details", {
            "fields": ("notes", "metadata"),
            "classes": ("collapse",)
        }),
    )

    def shipping_status(self, obj):
        """Display shipping status"""
        if hasattr(obj, 'shipping'):
            status = obj.shipping.status
            if status:
                color = {
                    'Order Created': 'orange',
                    'Courier Assigned': 'blue', 
                    'Pickup Scheduled': 'green',
                    'Shipped': 'purple',
                    'Delivered': 'darkgreen',
                    'Cancelled': 'red',
                }.get(status, 'gray')
                return format_html(
                    '<span style="color: {};">{}</span>',
                    color, status
                )
        return format_html('<span style="color: gray;">No Shipping</span>')
    
    def view_shipping_details(self, obj):
        """Link to shipping details"""
        if hasattr(obj, 'shipping'):
            url = reverse("admin:orders_shippingdetails_change", args=[obj.shipping.id])
            return format_html('<a href="{}">View Shipping</a>', url)
        return "No Shipping"
    
    shipping_status.short_description = "Shipping Status"
    view_shipping_details.short_description = "Shipping Details"

    def get_queryset(self, request):
        """Optimize queryset with related objects"""
        return super().get_queryset(request).select_related(
            'user', 'seller', 'shipping'
        ).prefetch_related('items')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_id", "name", "quantity", "final_price", "status")
    list_filter = ("status",)
    search_fields = ("order__order_number", "name", "product_id", "sku")
    raw_id_fields = ("order", "variant")
    readonly_fields = ("metadata",)


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
    search_fields = ("order__order_number", "full_name", "city", "state", "pincode")
    raw_id_fields = ("order",)


@admin.register(ShippingDetails)
class ShippingDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "provider",
        "awb_number",
        "courier_name", 
        "status",
        "expected_delivery",
        "courier_assigned",
        "pickup_scheduled_manually",
        "seller",
    )
    list_filter = (
        "provider", 
        "status", 
        "courier_assigned",
        "pickup_scheduled_manually",
        "is_return_order",
        "seller",
    )
    search_fields = (
        "order__order_number", 
        "awb_number", 
        "courier_name",
        "shipmojo_order_id",
        "lr_number",
    )
    raw_id_fields = ("order", "seller")
    readonly_fields = (
        "shipmojo_response", 
        "courier_assigned_at",
        "created_shipping_info",
    )
    
    fieldsets = (
        ("Basic Information", {
            "fields": (
                "order", "seller", "provider", "status",
                "weight", "length", "width", "height",
                "pickup_location"
            )
        }),
        ("Shipmojo Details", {
            "fields": (
                "shipmojo_order_id", "shipmojo_reference_id", 
                "warehouse_id", "awb_number", "lr_number"
            )
        }),
        ("Courier Information", {
            "fields": (
                "courier_name", "courier_company_service",
                "courier_company_id", "courier_assigned", 
                "courier_assigned_at"
            )
        }),
        ("Pickup & Delivery", {
            "fields": (
                "pickup_scheduled", "pickup_scheduled_manually",
                "expected_delivery", "tracking_url"
            )
        }),
        ("Return Order Details", {
            "fields": (
                "is_return_order", "return_reason_id", 
                "return_reason_comment", "customer_request"
            ),
            "classes": ("collapse",)
        }),
        ("Additional Data", {
            "fields": (
                "label_data", "status_updates", 
                "shipmojo_response"
            ),
            "classes": ("collapse",)
        }),
    )

    def created_shipping_info(self, obj):
        """Display formatted shipping creation info"""
        if obj.shipmojo_order_id:
            return format_html(
                '<strong>Shipmojo Order:</strong> {}<br>'
                '<strong>Reference:</strong> {}<br>'
                '<strong>Provider:</strong> {}',
                obj.shipmojo_order_id,
                obj.shipmojo_reference_id or 'N/A',
                obj.provider.title()
            )
        return "Not created in Shipmojo yet"
    
    created_shipping_info.short_description = "Shipping Info"

    actions = ['sync_tracking_status', 'generate_labels']

    def sync_tracking_status(self, request, queryset):
        """Sync tracking status for selected shipments"""
        from .ship import ShipmojoService
        
        updated = 0
        shipmojo_service = ShipmojoService()
        
        for shipping in queryset.filter(awb_number__isnull=False):
            try:
                tracking_response = shipmojo_service.track_order(shipping.awb_number)
                if "error" not in tracking_response and tracking_response.get("result") == "1":
                    tracking_data = tracking_response.get("data", {})
                    shipping.status = tracking_data.get("current_status", shipping.status)
                    shipping.expected_delivery = tracking_data.get("expected_delivery_date")
                    shipping.save()
                    updated += 1
            except Exception as e:
                continue
        
        self.message_user(request, f"Updated tracking status for {updated} shipments.")
    
    def generate_labels(self, request, queryset):
        """Generate labels for selected shipments"""
        from .ship import ShipmojoService
        
        generated = 0
        shipmojo_service = ShipmojoService()
        
        for shipping in queryset.filter(awb_number__isnull=False):
            try:
                label_response = shipmojo_service.get_order_label(shipping.awb_number)
                if "error" not in label_response and label_response.get("result") == "1":
                    label_data = label_response.get("data", [{}])[0]
                    shipping.label_data = label_data.get("label")
                    shipping.save()
                    generated += 1
            except Exception as e:
                continue
        
        self.message_user(request, f"Generated labels for {generated} shipments.")
    
    sync_tracking_status.short_description = "Sync tracking status"
    generate_labels.short_description = "Generate shipping labels"


@admin.register(ShipmentStatusUpdate)
class ShipmentStatusUpdateAdmin(admin.ModelAdmin):
    list_display = ("shipping", "status", "status_date", "location", "activity")
    list_filter = ("status", "status_date")
    search_fields = ("shipping__order__order_number", "status", "location", "activity")
    raw_id_fields = ("shipping",)
    readonly_fields = ("status_date",)
    date_hierarchy = "status_date"


@admin.register(PaymentDetails)
class PaymentDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "method", 
        "payment_status",
        "amount_paid",
        "transaction_id",
        "phonepe_status",
    )
    list_filter = ("method", "payment_status", "phonepe_status")
    search_fields = (
        "order__order_number", 
        "transaction_id",
        "phonepe_transaction_id",
    )
    raw_id_fields = ("order",)
    readonly_fields = ("phonepe_response",)


@admin.register(RefundDetails)
class RefundDetailsAdmin(admin.ModelAdmin):
    list_display = ("payment", "refund_id", "refund_amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("payment__order__order_number", "refund_id")
    raw_id_fields = ("payment",)
    readonly_fields = ("created_at", "updated_at")


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
    
    fieldsets = (
        ("Request Information", {
            "fields": ("order", "requested_by", "notes", "status")
        }),
        ("Processing", {
            "fields": ("seller_notes", "processed_at", "invoice_file")
        }),
        ("Timestamps", {
            "fields": ("requested_at",),
            "classes": ("collapse",)
        }),
    )


# Admin site customization
admin.site.site_header = "E-commerce Admin - Shipmojo Integration"
admin.site.site_title = "E-commerce Admin"
admin.site.index_title = "Welcome to E-commerce Administration"