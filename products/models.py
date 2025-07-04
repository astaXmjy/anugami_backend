"""
# models.py
# Complete implementation for Product models with shipping policy auto-caching
"""

from django.db import models
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    FileExtensionValidator,
)
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
import json
import logging

from customers.models import Customer
from system_users.models import CustomUser
from customers.models import Customer, CustomerActivity
from categories.models import Category

from .constants import (
    COLORS,
    SIZE_CHOICES,
    AGE_GROUP_CHOICES,
    GENDER_CHOICES,
    ATTRIBUTE_TYPES,
    PRODUCT_STATUS,
    MAX_STOCK_QUANTITY,
    MAX_UPLOAD_SIZE,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
)
from .validators import (
    validate_file_size,
    validate_image_type,
    validate_video_type,
    validate_price,
    validate_stock_quantity,
)

# Set up logging
logger = logging.getLogger(__name__)


class Brand(models.Model):
    """Brand model for products."""

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, max_length=255)
    description = models.TextField(null=True, blank=True)
    logo = models.URLField(null=True, blank=True)
    logo_storage_path = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Firebase Storage path for logo",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="brands_created", null=True
    )
    updated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, related_name="brands_updated", null=True
    )

    def save(self, *args, **kwargs):
        """Ensure slug is created from name."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]


class Product(models.Model):
    """Main product model with shipping policy auto-caching."""

    # Identifiers
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, max_length=255)
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)

    # Descriptions
    description = models.TextField(null=True, blank=True)
    short_description = models.TextField(null=True, blank=True)
    additional_description = models.TextField(null=True, blank=True)

    # Relationships
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")
    seller = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="products"
    )

    # Pricing
    regular_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[validate_price], default=0.00
    )
    sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[validate_price], default=0.00
    )
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[validate_price], default=0.00
    )

    # 🚚 SHIPPING POLICY FIELDS - Auto-caching functionality
    shipping_policy_id = models.CharField(max_length=255, null=True, blank=True)
    shipping_policy_data = models.JSONField(null=True, blank=True)

    # Tax & Commission
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    tax_included = models.BooleanField(default=True)
    hsn_code = models.CharField(max_length=20, null=True, blank=True)
    sac_code = models.CharField(max_length=20, null=True, blank=True)

    # Inventory
    stock_quantity = models.IntegerField(
        default=0, validators=[validate_stock_quantity]
    )
    low_stock_threshold = models.IntegerField(default=5)
    allow_backorder = models.BooleanField(default=False)
    is_digital = models.BooleanField(default=False)

    # Status & Display
    status = models.CharField(max_length=20, choices=PRODUCT_STATUS, default="draft")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    # SEO
    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    meta_keywords = models.JSONField(null=True, blank=True)

    # Dimensions
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    length = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    width = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    height = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    # Timestamps and Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="products_created",
        null=True,
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="products_updated",
        null=True,
    )

    view_count = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        """Ensure slug, SKU, and shipping policy cache are set."""
        # Generate slug if not set
        if not self.slug:
            self.slug = slugify(self.name)

        # Generate SKU if not set
        if not self.sku:
            self.sku = f"PRD-{uuid.uuid4().hex[:8]}"

        # 🚚 AUTO-CACHE SHIPPING POLICY DATA
        # Check if shipping_policy_id is set but shipping_policy_data is missing
        if self.shipping_policy_id and not self.shipping_policy_data:
            logger.info(f"🔄 Auto-caching shipping policy for product {self.name}")
            self.update_shipping_policy_cache()

        super().save(*args, **kwargs)

    def update_shipping_policy_cache(self):
        """🚚 Fetch and cache shipping policy data automatically"""
        if not self.shipping_policy_id:
            # Clear cache if no policy ID
            self.shipping_policy_data = None
            logger.info(f"🧹 Cleared shipping policy cache for product {self.id}")
            return

        try:
            # Import here to avoid circular imports
            from shipping_policies.models import ShippingPolicy
            from shipping_policies.serializers import ShippingPolicySerializer

            # Fetch the policy
            policy = ShippingPolicy.objects.get(id=self.shipping_policy_id)

            # Serialize the policy data
            serializer = ShippingPolicySerializer(policy)
            self.shipping_policy_data = serializer.data

            logger.info(
                f"✅ Updated shipping policy cache for product {self.id}: {policy.title}"
            )
            print(
                f"✅ Cached shipping policy '{policy.title}' for product '{self.name}'"
            )

        except Exception as e:
            logger.error(
                f"❌ Error caching shipping policy data for product {self.id}: {str(e)}"
            )
            print(f"❌ Error caching shipping policy: {str(e)}")
            self.shipping_policy_data = None

    def clear_shipping_policy_cache(self):
        """🗑️ Clear shipping policy cache"""
        self.shipping_policy_id = None
        self.shipping_policy_data = None
        logger.info(f"🗑️ Cleared shipping policy cache for product {self.id}")

    def update_stock(self, quantity_change):
        """Update stock quantity with validation."""
        new_quantity = self.stock_quantity + quantity_change

        if new_quantity < 0 and not self.allow_backorder:
            raise ValidationError(
                "Cannot reduce stock below zero without backorder enabled"
            )

        self.stock_quantity = new_quantity
        self.save()

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["category"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["is_active", "status"]),
            models.Index(fields=["-created_at"]),
            models.Index(
                fields=["shipping_policy_id"]
            ),  # Add index for shipping policy
        ]
        ordering = ["-created_at"]


class ProductImage(models.Model):
    """Product images metadata."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image_url = models.URLField(max_length=500)  # Firebase Storage URL
    storage_path = models.CharField(max_length=255, help_text="Firebase Storage path")
    alt_text = models.CharField(max_length=255, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Add this field to associate image with a specific color variant
    color_attribute = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Color value this image belongs to",
    )

    def save(self, *args, **kwargs):
        """Ensure only one primary image per product-color combination."""
        if self.is_primary:
            # Set all other images with same product and color to not primary
            self.__class__.objects.filter(
                product=self.product, color_attribute=self.color_attribute
            ).exclude(pk=self.pk).update(is_primary=False)

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["product", "is_primary", "sort_order"]),
            models.Index(fields=["color_attribute"]),
        ]


class ProductVideo(models.Model):
    """Product video metadata."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="videos"
    )
    video_url = models.URLField(max_length=500)  # Firebase Storage URL
    storage_path = models.CharField(max_length=255, help_text="Firebase Storage path")
    thumbnail_url = models.URLField(max_length=500, null=True, blank=True)
    thumbnail_storage_path = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Firebase Storage path for thumbnail",
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    duration = models.IntegerField(
        null=True, blank=True, help_text="Duration in seconds"
    )
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order"]
        indexes = [models.Index(fields=["product", "is_featured", "sort_order"])]


class ProductAttribute(models.Model):
    """Product specific attributes."""

    ATTRIBUTE_TYPES = [
        ("size", "Size"),
        ("color", "Color"),
        ("age_group", "Age Group"),
        ("gender", "Gender"),
        ("custom", "Custom"),
    ]

    TYPES = [
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("select", "Select"),
        ("multi-select", "Multi-Select"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="attributes"
    )
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES)
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    display_value = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPES, default="text")
    is_visible = models.BooleanField(default=True)
    is_variation = models.BooleanField(default=False)
    is_searchable = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    def clean(self):
        """Validate and set display values based on attribute type."""
        if self.attribute_type == "size":
            size_dict = dict(SIZE_CHOICES)
            if self.value not in size_dict:
                raise ValidationError(
                    f"Invalid size value. Must be one of: {', '.join(size_dict.keys())}"
                )
            self.display_value = size_dict[self.value]

        elif self.attribute_type == "color":
            color_dict = dict(COLORS)
            if self.value not in color_dict:
                raise ValidationError(
                    f"Invalid color value. Must be one of: {', '.join(color_dict.keys())}"
                )
            self.display_value = color_dict[self.value]

        elif self.attribute_type == "age_group":
            age_dict = dict(AGE_GROUP_CHOICES)
            if self.value not in age_dict:
                raise ValidationError(
                    f"Invalid age group value. Must be one of: {', '.join(age_dict.keys())}"
                )
            self.display_value = age_dict[self.value]

        elif self.attribute_type == "gender":
            gender_dict = dict(GENDER_CHOICES)
            if self.value not in gender_dict:
                raise ValidationError(
                    f"Invalid gender value. Must be one of: {', '.join(gender_dict.keys())}"
                )
            self.display_value = gender_dict[self.value]

        if not self.display_value:
            self.display_value = self.value  # For custom attributes

    class Meta:
        indexes = [models.Index(fields=["product", "attribute_type", "value"])]
        ordering = ["sort_order"]


class ProductReview(models.Model):
    """Product reviews by users."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="product_reviews"
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["product", "user"]
        indexes = [
            models.Index(fields=["product", "is_approved"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]


class ProductStock(models.Model):
    """Stock tracking per product in different warehouses."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_entries"
    )
    warehouse = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.IntegerField(default=0)
    batch_number = models.CharField(max_length=100, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    # Change this line - add default=timezone.now
    created_at = models.DateTimeField(
        default=timezone.now
    )  # Changed from auto_now_add=True
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.warehouse or 'No Warehouse'}"


class CartItem(models.Model):
    """Shopping cart items."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_cart_items"
    )
    user = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="customer_cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    variant_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "product", "variant_id"]
        indexes = [
            models.Index(fields=["user", "product"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]


class WishlistItem(models.Model):
    """Wishlist items."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_wishlist_items"
    )
    user = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="cart_wishlist_items"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "product"]
        indexes = [
            models.Index(fields=["user", "product"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]


class OrderItem(models.Model):
    """Individual items within an order."""

    # Remove the direct relation to Order model
    order_id = models.CharField(
        max_length=255, help_text="Firestore Order Document ID"  # UUID length
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,  # Keep order history even if product is deleted
        null=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=255)  # Store name at time of order
    sku = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    variant_id = models.CharField(max_length=255, null=True, blank=True)
    # Store product data at time of order
    product_data = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Calculate total price before saving."""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["order_id", "product"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]


class ProductVariant(models.Model):
    """Product variant model for handling different combinations (color, size, etc.)"""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    # Variant identifiers
    sku = models.CharField(max_length=50, unique=True)

    # Inventory
    stock_quantity = models.IntegerField(
        default=0, validators=[validate_stock_quantity]
    )

    # Pricing (can override product price)
    price_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Amount to add or subtract from base product price",
    )
    has_custom_price = models.BooleanField(default=False)
    custom_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_price],
    )

    # Status
    is_active = models.BooleanField(default=True)

    # SEO and tracking fields
    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    variant_slug = models.SlugField(max_length=255, null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Ensure variant is saved properly with attribute handling"""
        # First check if this is a new object (no primary key yet)
        is_new = self.pk is None

        # Call the parent save method first to get a primary key
        super().save(*args, **kwargs)

        # Now that we have a primary key, we can safely access related objects
        # Only try to generate variant_slug or handle attributes if needed
        if not self.variant_slug:
            # If this is a saved object, we can access related attributes
            attrs_components = []
            color_attr = self.variant_attributes.filter(attribute_type="color").first()
            if color_attr:
                attrs_components.append(color_attr.value)

            size_attr = self.variant_attributes.filter(attribute_type="size").first()
            if size_attr:
                attrs_components.append(size_attr.value)

            # Generate slug if we have attributes
            if attrs_components and hasattr(self.product, "slug"):
                attr_string = "-".join(attrs_components)
                self.variant_slug = f"{self.product.slug}-{attr_string}".lower()

                # Save again with the new slug
                super().save(update_fields=["variant_slug"] if not is_new else None)

        # Get final price calculation based on attributes
        if self.has_custom_price and self.custom_price is not None:
            # Custom price overrides everything
            pass
        else:
            # Price adjustment logic
            try:
                self.final_price = (self.product.sale_price or 0) + (
                    self.price_adjustment or 0
                )
            except (AttributeError, TypeError):
                # Handle error cases gracefully
                self.final_price = self.price_adjustment or 0

    def __str__(self):
        variant_attrs = self.variant_attributes.all()
        attrs_str = ", ".join(
            [f"{attr.attribute_type}: {attr.display_value}" for attr in variant_attrs]
        )
        return f"{self.product.name} - {attrs_str}"

    def get_price(self):
        """Get the effective price for this variant"""
        if self.has_custom_price and self.custom_price is not None:
            return self.custom_price

        # Convert both to Decimal to ensure proper arithmetic
        from decimal import Decimal

        price_adj = Decimal(
            str(self.price_adjustment)
        )  # Convert float to Decimal properly
        return self.product.sale_price + price_adj

    def update_stock(self, quantity_change):
        """Update stock quantity with validation."""
        new_quantity = self.stock_quantity + quantity_change

        if new_quantity < 0 and not self.product.allow_backorder:
            raise ValidationError(
                "Cannot reduce stock below zero without backorder enabled"
            )

        self.stock_quantity = new_quantity
        self.save()

    class Meta:
        unique_together = [("product", "sku")]
        indexes = [
            models.Index(fields=["product", "sku"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["variant_slug"]),
            models.Index(fields=["-view_count"]),
            models.Index(fields=["-last_viewed_at"]),
        ]


class VariantAttribute(models.Model):
    """Attributes specific to a product variant"""

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="variant_attributes"
    )
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES)
    value = models.CharField(max_length=255)
    display_value = models.CharField(max_length=255, null=True, blank=True)
    attribute_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[validate_price],
        help_text="Specific price for this attribute (optional)",
    )

    def clean(self):
        """Validate and set display values based on attribute type."""
        if self.attribute_type == "size":
            size_dict = dict(SIZE_CHOICES)
            if self.value not in size_dict:
                # More flexible validation for sizes
                # Allow custom sizes but show available options
                available_sizes = list(size_dict.keys())
                clothing_sizes = [
                    s
                    for s in available_sizes
                    if s
                    in ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL"]
                ]
                shoe_sizes = [
                    s for s in available_sizes if s.startswith(("UK", "US", "EU"))
                ]
                pant_sizes = [s for s in available_sizes if s.isdigit()]

                error_msg = f'Invalid size value "{self.value}". Available options:\n'
                error_msg += f'Clothing: {", ".join(clothing_sizes)}\n'
                error_msg += f'Shoes: {", ".join(shoe_sizes[:15])}...\n'
                error_msg += f'Pants: {", ".join(pant_sizes)}'

                raise ValidationError(error_msg)
            else:
                self.display_value = size_dict[self.value]

        elif self.attribute_type == "color":
            color_dict = dict(COLORS)
            if self.value not in color_dict:
                raise ValidationError(
                    f"Invalid color value. Must be one of: {', '.join(color_dict.keys())}"
                )
            self.display_value = color_dict[self.value]

        elif self.attribute_type == "age_group":
            age_dict = dict(AGE_GROUP_CHOICES)
            if self.value not in age_dict:
                raise ValidationError(
                    f"Invalid age group value. Must be one of: {', '.join(age_dict.keys())}"
                )
            self.display_value = age_dict[self.value]

        elif self.attribute_type == "gender":
            gender_dict = dict(GENDER_CHOICES)
            if self.value not in gender_dict:
                raise ValidationError(
                    f"Invalid gender value. Must be one of: {', '.join(gender_dict.keys())}"
                )
            self.display_value = gender_dict[self.value]

        # Set display_value for custom attributes if not already set
        if not self.display_value:
            self.display_value = self.value

    def save(self, *args, **kwargs):
        if not self.display_value:
            self.clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = [("variant", "attribute_type")]
        indexes = [
            models.Index(fields=["variant", "attribute_type", "value"]),
        ]


class ProductFeatureRequest(models.Model):
    """Model for seller requests to feature their products"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="feature_requests"
    )

    # Request details
    reason = models.TextField(help_text="Reason for requesting to feature this product")
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_notes = models.TextField(blank=True, null=True)

    # Tracking fields
    requested_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="product_feature_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Review fields
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_product_feature_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Product Feature Request"
        verbose_name_plural = "Product Feature Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feature request for {self.product.name} by {self.requested_by.email}"

    def approve(self, admin_user, admin_notes=None):
        """Approve the request and mark the product as featured"""
        self.status = "approved"
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        if admin_notes:
            self.admin_notes = admin_notes

        # Mark the product as featured
        self.product.is_featured = True
        self.product.save()

        self.save()

    def reject(self, admin_user, admin_notes=None):
        """Reject the request"""
        self.status = "rejected"
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        if admin_notes:
            self.admin_notes = admin_notes
        self.save()


class RecentlyViewedProduct(models.Model):
    """Track recently viewed products with variant information"""

    user = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="recently_viewed_products"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="recent_views"
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        related_name="recent_views",
        null=True,
        blank=True,
    )
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "product")]
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["-viewed_at"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user} viewed {self.product.name}"


# 🚀 SHIPPING POLICY SIGNAL HANDLERS
# These signals ensure that shipping policy data is always synchronized


def update_products_on_policy_change(sender, instance, created, **kwargs):
    """
    Signal handler to update all products when a shipping policy is modified
    """
    try:
        # Import here to avoid circular imports
        from shipping_policies.serializers import ShippingPolicySerializer

        # Get all products using this policy
        products = Product.objects.filter(shipping_policy_id=str(instance.id))

        if products.exists():
            # Serialize the updated policy
            serializer = ShippingPolicySerializer(instance)
            policy_data = serializer.data

            # Update all products using this policy
            updated_count = 0
            for product in products:
                product.shipping_policy_data = policy_data
                product.save(update_fields=["shipping_policy_data"])
                updated_count += 1

            logger.info(
                f"✅ Updated {updated_count} products with policy: {instance.title}"
            )
            print(f"✅ Auto-updated {updated_count} products with policy changes")

    except Exception as e:
        logger.error(f"❌ Error updating products on policy change: {str(e)}")
        print(f"❌ Error updating products on policy change: {str(e)}")


def clear_products_on_policy_delete(sender, instance, **kwargs):
    """
    Signal handler to clear shipping policy data from products when a policy is deleted
    """
    try:
        # Get all products using this policy
        products = Product.objects.filter(shipping_policy_id=str(instance.id))

        if products.exists():
            updated_count = 0
            for product in products:
                product.shipping_policy_id = None
                product.shipping_policy_data = None
                product.save(
                    update_fields=["shipping_policy_id", "shipping_policy_data"]
                )
                updated_count += 1

            logger.info(f"🗑️ Cleared policy reference from {updated_count} products")
            print(f"🗑️ Cleared policy reference from {updated_count} products")

    except Exception as e:
        logger.error(f"❌ Error clearing products on policy delete: {str(e)}")
        print(f"❌ Error clearing products on policy delete: {str(e)}")


# 📡 CONNECT SIGNALS (This will be imported by apps.py)
def connect_shipping_policy_signals():
    """
    Connect shipping policy signals to ensure automatic updates
    """
    from django.db.models.signals import post_save, post_delete

    try:
        # Import ShippingPolicy model
        from shipping_policies.models import ShippingPolicy

        # Connect the signals
        post_save.connect(
            update_products_on_policy_change,
            sender=ShippingPolicy,
            dispatch_uid="update_products_on_policy_change",
        )

        post_delete.connect(
            clear_products_on_policy_delete,
            sender=ShippingPolicy,
            dispatch_uid="clear_products_on_policy_delete",
        )

        logger.info("✅ Shipping policy signals connected successfully")
        print("✅ Shipping policy signals connected successfully")

    except ImportError:
        logger.warning("⚠️ ShippingPolicy model not found - signals not connected")
        print("⚠️ ShippingPolicy model not found - signals not connected")
    except Exception as e:
        logger.error(f"❌ Error connecting shipping policy signals: {str(e)}")
        print(f"❌ Error connecting shipping policy signals: {str(e)}")


# 🛠️ UTILITY FUNCTIONS FOR SHIPPING POLICY MANAGEMENT


def fix_missing_shipping_policy_cache():
    """
    Utility function to fix products that have shipping_policy_id but no shipping_policy_data
    This can be called from a management command or admin action
    """
    products_to_fix = Product.objects.filter(
        shipping_policy_id__isnull=False, shipping_policy_data__isnull=True
    )

    fixed_count = 0
    error_count = 0

    for product in products_to_fix:
        try:
            product.update_shipping_policy_cache()
            product.save(update_fields=["shipping_policy_data"])
            fixed_count += 1
            print(f"✅ Fixed: {product.name}")
        except Exception as e:
            error_count += 1
            print(f"❌ Error fixing {product.name}: {str(e)}")

    print(f"\n🎉 Fixed {fixed_count} products, {error_count} errors")
    return fixed_count, error_count


def validate_shipping_policy_cache():
    """
    Utility function to validate that all products with shipping_policy_id have valid shipping_policy_data
    """
    products_with_policy = Product.objects.filter(shipping_policy_id__isnull=False)

    valid_count = 0
    invalid_count = 0

    for product in products_with_policy:
        if product.shipping_policy_data:
            valid_count += 1
        else:
            invalid_count += 1
            print(f"⚠️ Product '{product.name}' has policy ID but no policy data")

    print(f"\n📊 Validation Results: {valid_count} valid, {invalid_count} invalid")
    return valid_count, invalid_count
