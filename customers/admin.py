from django.contrib import admin

# customers/admin.py
from django.contrib import admin
from .models import (
    Customer,
    Address,
    CartItem,
    WishlistItem,
    CustomerPreferences,
    CustomerActivity,
    CustomerTransaction,
    CustomerOrderStats,
)


class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "email",
        "phone",
        "status",
        "wallet_balance",
        "total_orders",
    )
    list_filter = ("status", "gender", "is_phone_verified")
    search_fields = ("full_name", "user__email", "user__phone_number", "firebase_uid")
    readonly_fields = ("created_at", "updated_at", "last_active")
    fieldsets = (
        (
            "Basic Info",
            {
                "fields": (
                    "user",
                    "full_name",
                    "date_of_birth",
                    "gender",
                    "profile_picture",
                )
            },
        ),
        ("Authentication", {"fields": ("firebase_uid", "is_phone_verified")}),
        ("Status", {"fields": ("status", "last_active")}),
        (
            "Financial",
            {
                "fields": (
                    "wallet_balance",
                    "reward_points",
                    "total_orders",
                    "total_order_value",
                )
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def email(self, obj):
        return obj.user.email if obj.user else None

    email.short_description = "Email"

    def phone(self, obj):
        return obj.user.phone_number if obj.user else None

    phone.short_description = "Phone"


class AddressAdmin(admin.ModelAdmin):
    list_display = ("customer", "full_name", "city", "state", "pincode", "is_default")
    list_filter = ("address_type", "city", "state", "country")
    search_fields = ("customer__full_name", "street", "city", "pincode")
    raw_id_fields = ("customer",)


class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "product_id",
        "variant_id",
        "quantity",
        "price",
        "total_price",
    )
    list_filter = ("customer",)
    search_fields = ("customer__full_name", "product_id", "variant_id")
    raw_id_fields = ("customer",)

    def total_price(self, obj):
        return obj.quantity * obj.price

    total_price.short_description = "Total"


class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("customer", "product_id", "variant_id", "added_at")
    list_filter = ("customer",)
    search_fields = ("customer__full_name", "product_id", "variant_id")
    raw_id_fields = ("customer",)


class CustomerPreferencesAdmin(admin.ModelAdmin):
    list_display = ("customer", "currency", "language")
    search_fields = ("customer__full_name",)
    raw_id_fields = ("customer",)


class CustomerActivityAdmin(admin.ModelAdmin):
    list_display = ("customer", "interaction_type", "product_id", "timestamp")
    list_filter = ("interaction_type", "customer")
    search_fields = ("customer__full_name", "product_id", "category_id")
    raw_id_fields = ("customer",)
    readonly_fields = ("timestamp",)


class CustomerTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "transaction_type",
        "amount",
        "transaction_id",
        "created_at",
    )
    list_filter = ("transaction_type", "customer")
    search_fields = ("customer__full_name", "transaction_id")
    raw_id_fields = ("customer",)
    readonly_fields = ("created_at",)


class CustomerOrderStatsAdmin(admin.ModelAdmin):
    list_display = ("customer", "total_orders", "total_order_value", "last_order_date")
    search_fields = ("customer__full_name",)
    raw_id_fields = ("customer",)


# Register models with their admin classes
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(CartItem, CartItemAdmin)
admin.site.register(WishlistItem, WishlistItemAdmin)
admin.site.register(CustomerPreferences, CustomerPreferencesAdmin)
admin.site.register(CustomerActivity, CustomerActivityAdmin)
admin.site.register(CustomerTransaction, CustomerTransactionAdmin)
admin.site.register(CustomerOrderStats, CustomerOrderStatsAdmin)
