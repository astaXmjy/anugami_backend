from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.http import urlencode
from django.contrib.auth.admin import UserAdmin
from .models import Seller, ShippingLocation, Order


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "email",
        "status",
        "is_email_verified",
        "is_phone_verified",
        "is_document_verified",
        "view_pan_card",
        "view_orders",
        "view_locations",
    )
    list_filter = (
        "status",
        "is_email_verified",
        "is_phone_verified",
        "is_document_verified",
    )
    search_fields = ("business_name", "email", "phone", "pan_number")
    actions = ["approve_sellers", "reject_sellers", "verify_documents"]

    def approve_sellers(self, request, queryset):
        """Approve selected sellers"""
        queryset.update(status="approved")

    def reject_sellers(self, request, queryset):
        """Reject selected sellers"""
        queryset.update(status="rejected")

    def verify_documents(self, request, queryset):
        """Verify documents for selected sellers"""
        queryset.update(is_document_verified=True)

    def view_pan_card(self, obj):
        """Link to seller's PAN card"""
        if obj.pan_document_url:
            return format_html(
                '<a href="{}" target="_blank">View PAN Card</a>', obj.pan_document_url
            )
        return "No PAN Card"

    def view_orders(self, obj):
        """Link to seller's orders in admin"""
        url = (
            reverse("admin:sellers_order_changelist")
            + "?"
            + urlencode({"seller__id": obj.id})
        )
        return format_html('<a href="{}">View Orders</a>', url)

    def view_locations(self, obj):
        """Link to seller's shipping locations in admin"""
        url = (
            reverse("admin:sellers_shippinglocation_changelist")
            + "?"
            + urlencode({"seller__id": obj.id})
        )
        return format_html('<a href="{}">View Locations</a>', url)

    view_pan_card.short_description = "PAN Card"
    view_orders.short_description = "Orders"
    view_locations.short_description = "Shipping Locations"
    verify_documents.short_description = "Verify Documents"


@admin.register(ShippingLocation)
class ShippingLocationAdmin(admin.ModelAdmin):
    list_display = ("seller", "address", "city", "state", "pincode", "phone_number")
    search_fields = ("seller__business_name", "city", "state", "pincode")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "seller",
        "customer_name",
        "total_price",
        "order_status",
        "created_at",
    )
    list_filter = ("order_status", "created_at")
    search_fields = ("customer_name", "seller__business_name", "order_status")
