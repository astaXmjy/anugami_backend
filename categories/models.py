# categories/models.py
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from mptt.models import MPTTModel, TreeForeignKey
from system_users.models import CustomUser
import uuid
from django.contrib.postgres.fields import ArrayField


class Category(MPTTModel):
    """Main category model with hierarchical structure using MPTT."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    short_description = models.TextField(blank=True, null=True)
    parent = TreeForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )

    # Display Settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    show_in_menu = models.BooleanField(default=True)
    menu_order = models.IntegerField(default=0)
    display_order = models.IntegerField(default=0)

    # Counters
    product_count = models.IntegerField(default=0)
    subcategory_count = models.IntegerField(default=0)

    # Financial Settings
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Media & Assets
    image_url = models.URLField(max_length=255, null=True, blank=True)
    icon_url = models.URLField(max_length=255, null=True, blank=True)
    banner_url = models.URLField(max_length=255, null=True, blank=True)

    # URL Settings
    custom_url = models.URLField(max_length=500, blank=True, null=True)
    redirect_url = models.URLField(max_length=500, blank=True, null=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="categories_created",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="categories_updated",
    )

    class MPTTMeta:
        order_insertion_by = ["menu_order", "name"]

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["tree_id", "lft"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        # Validate parent
        if self.parent and self.parent.id == self.id:
            raise ValidationError("Category cannot be its own parent")

        super().save(*args, **kwargs)

        # Update parent's subcategory count
        if self.parent:
            self.parent.subcategory_count = self.parent.get_children().count()
            self.parent.save()


class CategorySEO(models.Model):
    """SEO settings for a category."""

    category = models.OneToOneField(
        Category, on_delete=models.CASCADE, related_name="seo"
    )
    page_title = models.CharField(max_length=255, blank=True, null=True)
    meta_description = models.TextField(blank=True, null=True)
    meta_keywords = ArrayField(models.CharField(max_length=100), blank=True, null=True)
    og_title = models.CharField(max_length=255, blank=True, null=True)
    og_description = models.TextField(blank=True, null=True)
    og_image = models.ImageField(
        upload_to="categories/og_images/", blank=True, null=True
    )
    canonical_url = models.URLField(max_length=500, blank=True, null=True)
    robots_meta = models.CharField(max_length=100, default="index, follow")
    schema_markup = models.JSONField(blank=True, null=True)

    def clean(self):
        if not self.page_title and self.category:
            self.page_title = self.category.name
        if not self.og_title:
            self.og_title = self.page_title

    class Meta:
        verbose_name = "Category SEO"
        verbose_name_plural = "Category SEO"


class CategoryImage(models.Model):
    """Category images with metadata."""

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="images"
    )
    image = models.URLField(max_length=255, null=True, blank=True)
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    file_size = models.IntegerField(blank=True, null=True)  # Size in bytes
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure only one primary image per category
        if self.is_primary:
            self.__class__.objects.filter(
                category=self.category, is_primary=True
            ).update(is_primary=False)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["sort_order", "-is_primary", "created_at"]
        verbose_name = "Category Image"
        verbose_name_plural = "Category Images"


class CategoryAttribute(models.Model):
    """Product attributes specific to a category."""

    ATTRIBUTE_TYPES = [
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("select", "Select"),
        ("multi-select", "Multi Select"),
        ("date", "Date"),
        ("color", "Color"),
        ("size", "Size"),
    ]

    FILTER_TYPES = [
        ("range", "Range"),
        ("exact", "Exact Match"),
        ("multi", "Multiple Values"),
    ]

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="attributes"
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES)
    is_required = models.BooleanField(default=False)
    is_filter = models.BooleanField(default=False)
    filter_type = models.CharField(
        max_length=20, choices=FILTER_TYPES, blank=True, null=True
    )
    options = ArrayField(models.CharField(max_length=100), blank=True, null=True)
    validation = models.JSONField(blank=True, null=True)  # JSON for validation rules
    default_value = models.CharField(max_length=255, blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    help_text = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = ["category", "name"]
        verbose_name = "Category Attribute"
        verbose_name_plural = "Category Attributes"

class CategoryRequest(models.Model):
    """Model for seller category creation requests"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="category_requests"
    )
    
    # Metadata
    requested_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="category_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, null=True)
    
    # Approval details
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_category_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Category Request"
        verbose_name_plural = "Category Requests"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) - by {self.requested_by.email}"        


