from django.contrib import admin
from .models import ShippingPolicy, ShippingZone


class ShippingZoneInline(admin.TabularInline):
    model = ShippingZone
    extra = 1
    fields = ("name", "states", "shipping_cost", "estimated_days")


@admin.register(ShippingPolicy)
class ShippingPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "seller",
        "shipping_cost",
        "is_active",
        "is_default",
        "created_at",
    )
    list_filter = ("is_active", "is_default", "seller")
    search_fields = ("title", "description", "seller__name")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    inlines = [ShippingZoneInline]

    fieldsets = (
        (
            "Policy Information",
            {"fields": ("title", "description", "return_policy", "delivery_time")},
        ),
        ("Pricing", {"fields": ("shipping_cost", "max_weight")}),
        ("Status", {"fields": ("is_active", "is_default", "seller")}),
        (
            "Audit Information",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Track user who creates/updates policy"""
        if not change:  # If creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Save inline shipping zones"""
        instances = formset.save(commit=False)
        for instance in instances:
            instance.save()
        formset.save_m2m()


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "policy", "shipping_cost", "estimated_days")
    list_filter = ("policy__seller",)
    search_fields = ("name", "policy__title")
