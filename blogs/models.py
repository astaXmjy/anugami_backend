from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from system_users.models import CustomUser


class BlogCategory(models.Model):
    """Blog category model"""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Blog Category")
        verbose_name_plural = _("Blog Categories")
        ordering = ["name"]


class BlogTag(models.Model):
    """Blog tags model"""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, max_length=50)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class BlogPost(models.Model):
    """Blog post model"""

    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("published", _("Published")),
        ("archived", _("Archived")),
    ]

    # Basic Fields
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    content = models.TextField()
    excerpt = models.TextField(null=True, blank=True)

    # Relationships
    category = models.ForeignKey(
        BlogCategory, on_delete=models.SET_NULL, null=True, related_name="posts"
    )
    author = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="blog_posts"
    )
    tags = models.ManyToManyField(BlogTag, related_name="blog_posts", blank=True)

    # Featured Image
    featured_image_url = models.URLField(max_length=500, null=True, blank=True)
    featured_image_storage_path = models.CharField(
        max_length=255, null=True, blank=True, help_text="Firebase Storage path"
    )

    # Status and Stats
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_featured = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)

    # SEO Fields
    meta_title = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        help_text="Maximum 60 characters for optimal SEO",
    )
    meta_description = models.TextField(
        max_length=160,
        null=True,
        blank=True,
        help_text="Maximum 160 characters for optimal SEO",
    )
    meta_keywords = models.CharField(
        max_length=255, null=True, blank=True, help_text="Comma-separated keywords"
    )
    canonical_url = models.URLField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Override default canonical URL",
    )
    og_image = models.URLField(
        max_length=255, null=True, blank=True, help_text="Custom Open Graph image URL"
    )
    structured_data = models.JSONField(
        null=True, blank=True, help_text="Additional structured data in JSON-LD format"
    )
    robots_meta = models.CharField(
        max_length=50,
        default="index, follow",
        help_text="Custom robots meta tag content",
    )

    # Timestamps and Audit
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="blogs_created"
    )
    updated_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="blogs_updated"
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Blog Post")
        verbose_name_plural = _("Blog Posts")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]


class BlogImage(models.Model):
    """Blog post images model"""

    blog_post = models.ForeignKey(
        BlogPost, on_delete=models.CASCADE, related_name="images"
    )
    image_url = models.URLField(max_length=500)
    storage_path = models.CharField(max_length=255, help_text="Firebase Storage path")
    alt_text = models.CharField(max_length=255, null=True, blank=True)
    caption = models.CharField(max_length=255, null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order"]
        indexes = [models.Index(fields=["blog_post", "sort_order"])]


class BlogComment(models.Model):
    """Blog comments model"""

    blog_post = models.ForeignKey(
        BlogPost, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    author = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="blog_comments"
    )
    content = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["blog_post", "-created_at"])]
