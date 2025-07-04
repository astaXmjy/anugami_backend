# admin.py - Complete admin interface for product management

from django.contrib import admin
from django.utils.html import format_html
from django import forms
from .models import (
    Product,
    ProductImage,
    ProductVideo,
    ProductAttribute,
    ProductReview,
    Brand,
    ProductStock,
    ProductVariant,
    VariantAttribute,
    ProductFeatureRequest,
    RecentlyViewedProduct,
)


class ProductAdminForm(forms.ModelForm):
    """Custom form for Product admin"""

    class Meta:
        model = Product
        fields = "__all__"
        exclude = ["slug"]  # Exclude slug from form fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ProductAttributeInline(admin.TabularInline):
    """Inline admin for Product Attributes"""

    model = ProductAttribute
    extra = 1
    fields = (
        "attribute_type",
        "name",
        "value",
        "display_value",
        "is_visible",
        "sort_order",
    )
    readonly_fields = ("display_value",)


class ProductImageInline(admin.TabularInline):
    """Inline admin for Product Images"""

    model = ProductImage
    extra = 1
    fields = (
        "image_url",
        "color_attribute",
        "alt_text",
        "is_primary",
        "sort_order",
        "image_preview",
    )
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        """Generate image preview in admin"""
        if obj.image_url:
            return format_html(
                f'<img src="{obj.image_url}" style="max-height: 100px; max-width: 100px;" />'
            )
        return ""

    image_preview.short_description = "Preview"


class ProductVideoInline(admin.TabularInline):
    """Inline admin for Product Videos"""

    model = ProductVideo
    extra = 1
    fields = (
        "video_url",
        "title",
        "thumbnail_url",
        "is_featured",
        "sort_order",
        "video_preview",
    )
    readonly_fields = ["video_preview"]

    def video_preview(self, obj):
        """Generate video thumbnail preview in admin"""
        if obj.thumbnail_url:
            return format_html(
                f'<img src="{obj.thumbnail_url}" style="max-height: 100px; max-width: 100px;" />'
            )
        return ""

    video_preview.short_description = "Thumbnail"


class ProductStockInline(admin.TabularInline):
    """Inline admin for Product Stock"""

    model = ProductStock
    extra = 1
    fields = ("warehouse", "quantity", "batch_number", "expiry_date")


class VariantAttributeInline(admin.TabularInline):
    """Inline admin for Variant Attributes"""

    model = VariantAttribute
    extra = 1
    fields = ("attribute_type", "value", "display_value", "attribute_price")
    readonly_fields = ("display_value",)


class ProductVariantInline(admin.TabularInline):
    """Inline admin for Product Variants"""

    model = ProductVariant
    extra = 1
    show_change_link = True
    fields = (
        "sku",
        "stock_quantity",
        "price_adjustment",
        "has_custom_price",
        "custom_price",
        "is_active",
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Admin configuration for ProductVariant model"""

    list_display = (
        "product",
        "sku",
        "get_variant_attributes",
        "stock_quantity",
        "get_price",
        "is_active",
        "view_count",
        "last_viewed_at",
    )
    list_filter = ("is_active", "has_custom_price", "created_at")
    search_fields = ("sku", "product__name", "variant_slug")
    inlines = [VariantAttributeInline]
    readonly_fields = ("created_at", "updated_at", "view_count", "last_viewed_at")

    fieldsets = (
        ("Basic Information", {"fields": ("product", "sku", "variant_slug")}),
        ("Inventory", {"fields": ("stock_quantity", "is_active")}),
        (
            "Pricing",
            {"fields": ("price_adjustment", "has_custom_price", "custom_price")},
        ),
        (
            "SEO & Tracking",
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                    "view_count",
                    "last_viewed_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_variant_attributes(self, obj):
        """Display variant attributes"""
        attrs = obj.variant_attributes.all()
        return ", ".join(
            [f"{attr.attribute_type}: {attr.display_value}" for attr in attrs]
        )

    get_variant_attributes.short_description = "Attributes"

    def get_price(self, obj):
        """Display calculated price"""
        return f"${obj.get_price():.2f}"

    get_price.short_description = "Final Price"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin configuration for Product model"""

    form = ProductAdminForm
    list_display = [
        "name",
        "sku",
        "brand",
        "category",
        "seller",
        "regular_price",
        "sale_price",
        "stock_quantity",
        "status",
        "is_active",
        "is_featured",
        "view_count",
    ]
    list_filter = [
        "status",
        "is_active",
        "is_featured",
        "brand",
        "category",
        "seller",
        "created_at",
    ]
    search_fields = ["name", "sku", "description", "brand__name", "category__name"]
    inlines = [
        ProductAttributeInline,
        ProductImageInline,
        ProductVideoInline,
        ProductStockInline,
        ProductVariantInline,
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "slug",
        "view_count",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "slug",
                    "sku",
                    "description",
                    "short_description",
                    "additional_description",
                )
            },
        ),
        ("Relationships", {"fields": ("category", "brand", "seller")}),
        (
            "Pricing",
            {"fields": ("regular_price", "sale_price", "cost_price", "tax_included")},
        ),
        (
            "Tax & Commission",
            {
                "fields": ("gst_rate", "commission_rate", "hsn_code", "sac_code"),
                "classes": ("collapse",),
            },
        ),
        (
            "Inventory",
            {
                "fields": (
                    "stock_quantity",
                    "low_stock_threshold",
                    "allow_backorder",
                    "is_digital",
                )
            },
        ),
        (
            "Status & Display",
            {"fields": ("status", "is_active", "is_featured", "view_count")},
        ),
        (
            "Dimensions",
            {
                "fields": ("weight", "length", "width", "height"),
                "classes": ("collapse",),
            },
        ),
        (
            "SEO & Metadata",
            {
                "fields": ("meta_title", "meta_description", "meta_keywords"),
                "classes": ("collapse",),
            },
        ),
        (
            "Shipping",
            {
                "fields": ("shipping_policy_id", "shipping_policy_data"),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit Trail",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["mark_as_featured", "mark_as_active", "mark_as_inactive"]

    def save_model(self, request, obj, form, change):
        """Set created_by and updated_by on save"""
        if not change:  # Creating a new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def mark_as_featured(self, request, queryset):
        """Mark selected products as featured"""
        queryset.update(is_featured=True)
        self.message_user(request, f"{queryset.count()} products marked as featured")

    mark_as_featured.short_description = "Mark selected products as featured"

    def mark_as_active(self, request, queryset):
        """Mark selected products as active"""
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} products marked as active")

    mark_as_active.short_description = "Mark selected products as active"

    def mark_as_inactive(self, request, queryset):
        """Mark selected products as inactive"""
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} products marked as inactive")

    mark_as_inactive.short_description = "Mark selected products as inactive"


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Admin configuration for ProductImage model"""

    list_display = [
        "product",
        "color_attribute",
        "is_primary",
        "sort_order",
        "created_at",
        "image_preview",
    ]
    list_filter = ["is_primary", "color_attribute", "created_at"]
    search_fields = ["product__name", "alt_text"]
    readonly_fields = ["image_preview", "created_at"]

    def image_preview(self, obj):
        """Display image preview"""
        if obj.image_url:
            return format_html(
                f'<img src="{obj.image_url}" style="max-height: 150px; max-width: 150px;" />'
            )
        return ""

    image_preview.short_description = "Preview"


@admin.register(ProductVideo)
class ProductVideoAdmin(admin.ModelAdmin):
    """Admin configuration for ProductVideo model"""

    list_display = [
        "product",
        "title",
        "is_featured",
        "sort_order",
        "duration",
        "created_at",
    ]
    list_filter = ["is_featured", "created_at"]
    search_fields = ["product__name", "title"]
    readonly_fields = ["created_at"]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin configuration for Brand model"""

    list_display = ["name", "slug", "is_active", "created_at", "logo_preview"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at", "logo_preview"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "slug", "description", "is_active")}),
        ("Branding", {"fields": ("logo", "logo_storage_path", "logo_preview")}),
        (
            "Audit Trail",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def logo_preview(self, obj):
        """Display logo preview"""
        if obj.logo:
            return format_html(
                f'<img src="{obj.logo}" style="max-height: 100px; max-width: 100px;" />'
            )
        return ""

    logo_preview.short_description = "Logo Preview"


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    """Admin configuration for ProductAttribute model"""

    list_display = [
        "product",
        "attribute_type",
        "name",
        "value",
        "display_value",
        "is_visible",
        "sort_order",
    ]
    list_filter = ["attribute_type", "is_visible", "is_variation", "is_searchable"]
    search_fields = ["product__name", "name", "value"]
    readonly_fields = ["display_value"]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    """Admin configuration for ProductReview model"""

    list_display = [
        "product",
        "user",
        "rating",
        "is_verified",
        "is_approved",
        "created_at",
    ]
    list_filter = ["is_verified", "is_approved", "rating", "created_at"]
    search_fields = ["product__name", "user__email", "title", "comment"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["approve_reviews", "mark_as_verified", "reject_reviews"]

    def approve_reviews(self, request, queryset):
        """Bulk approve reviews"""
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} reviews approved")

    approve_reviews.short_description = "Approve selected reviews"

    def mark_as_verified(self, request, queryset):
        """Bulk mark reviews as verified"""
        queryset.update(is_verified=True)
        self.message_user(request, f"{queryset.count()} reviews marked as verified")

    mark_as_verified.short_description = "Mark selected reviews as verified"

    def reject_reviews(self, request, queryset):
        """Bulk reject reviews"""
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} reviews rejected")

    reject_reviews.short_description = "Reject selected reviews"


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    """Admin configuration for ProductStock model"""

    list_display = [
        "product",
        "warehouse",
        "quantity",
        "batch_number",
        "expiry_date",
        "created_at",
    ]
    list_filter = ["warehouse", "expiry_date", "created_at"]
    search_fields = ["product__name", "warehouse", "batch_number"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(VariantAttribute)
class VariantAttributeAdmin(admin.ModelAdmin):
    """Admin configuration for VariantAttribute model"""

    list_display = [
        "variant",
        "attribute_type",
        "value",
        "display_value",
        "attribute_price",
    ]
    list_filter = ["attribute_type"]
    search_fields = ["variant__sku", "variant__product__name", "value"]
    readonly_fields = ["display_value"]


@admin.register(ProductFeatureRequest)
class ProductFeatureRequestAdmin(admin.ModelAdmin):
    """Admin configuration for ProductFeatureRequest model"""

    list_display = [
        "product",
        "requested_by",
        "contact_name",
        "status",
        "created_at",
        "reviewed_by",
    ]
    list_filter = ["status", "created_at", "reviewed_at"]
    search_fields = [
        "product__name",
        "contact_name",
        "contact_email",
        "reason",
        "requested_by__email",
    ]
    readonly_fields = ["id", "created_at", "updated_at", "reviewed_at"]
    fieldsets = (
        (
            "Request Information",
            {"fields": ("product", "requested_by", "reason", "status")},
        ),
        (
            "Contact Details",
            {"fields": ("contact_name", "contact_email", "contact_phone")},
        ),
        (
            "Review Information",
            {"fields": ("reviewed_by", "reviewed_at", "admin_notes")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    actions = ["approve_requests", "reject_requests"]

    def approve_requests(self, request, queryset):
        """Bulk approve feature requests"""
        approved_count = 0
        for feature_request in queryset.filter(status="pending"):
            feature_request.approve(admin_user=request.user)
            approved_count += 1
        self.message_user(request, f"{approved_count} requests approved successfully")

    approve_requests.short_description = "Approve selected feature requests"

    def reject_requests(self, request, queryset):
        """Bulk reject feature requests"""
        rejected_count = 0
        for feature_request in queryset.filter(status="pending"):
            feature_request.reject(admin_user=request.user)
            rejected_count += 1
        self.message_user(request, f"{rejected_count} requests rejected")

    reject_requests.short_description = "Reject selected feature requests"


@admin.register(RecentlyViewedProduct)
class RecentlyViewedProductAdmin(admin.ModelAdmin):
    """Admin configuration for RecentlyViewedProduct model"""

    list_display = ["user", "product", "variant", "viewed_at"]
    list_filter = ["viewed_at"]
    search_fields = ["user__email", "product__name", "variant__sku"]
    readonly_fields = ["viewed_at"]

    def has_add_permission(self, request):
        """Disable manual addition of recently viewed products"""
        return False
