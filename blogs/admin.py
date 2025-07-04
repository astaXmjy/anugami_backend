from django.contrib import admin
from django.utils.html import format_html
from .models import BlogPost, BlogCategory, BlogImage, BlogComment, BlogTag


class BlogImageInline(admin.TabularInline):
    """Inline admin for Blog Images"""

    model = BlogImage
    extra = 1
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        """Generate image preview in admin"""
        if obj.image_url:
            return format_html(
                f'<img src="{obj.image_url}" style="max-height: 100px; max-width: 100px;" />'
            )
        return ""

    image_preview.short_description = "Preview"


class BlogCommentInline(admin.TabularInline):
    """Inline admin for Blog Comments"""

    model = BlogComment
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    """Admin configuration for Blog Category"""

    list_display = ["name", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """Admin configuration for Blog Post"""

    list_display = [
        "title",
        "author",
        "category",
        "status",
        "is_featured",
        "views_count",
        "created_at",
    ]
    list_filter = ["status", "is_featured", "category", "author"]
    search_fields = ["title", "content", "excerpt", "meta_keywords"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = [
        "views_count",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
    inlines = [BlogImageInline, BlogCommentInline]
    filter_horizontal = ("tags",)  # Keeps many-to-many field filtering

    fieldsets = (
        (None, {"fields": ("title", "slug")}),
        ("Content", {"fields": ("content", "excerpt"), "classes": ("full-width",)}),
        ("Categorization", {"fields": ("category", "author", "tags")}),
        (
            "Featured Image",
            {"fields": ("featured_image_url", "featured_image_storage_path")},
        ),
        ("Publishing", {"fields": ("status", "is_featured", "published_at")}),
        (
            "SEO",
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                    "meta_keywords",
                    "canonical_url",
                    "og_image",
                    "structured_data",
                    "robots_meta",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Statistics", {"fields": ("views_count",), "classes": ("collapse",)}),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )

    class Media:
        css = {"all": ("css/admin/blog-post.css",)}

    def save_model(self, request, obj, form, change):
        """Set created_by and updated_by on save"""
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    """Admin configuration for Blog Comment"""

    list_display = ["blog_post", "author", "is_approved", "created_at"]
    list_filter = ["is_approved", "created_at"]
    search_fields = ["content", "author__email", "blog_post__title"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["approve_comments"]

    def approve_comments(self, request, queryset):
        """Bulk approve comments"""
        queryset.update(is_approved=True)

    approve_comments.short_description = "Approve selected comments"


@admin.register(BlogTag)
class BlogTagAdmin(admin.ModelAdmin):
    """Admin configuration for Blog Tag"""

    list_display = ["name", "slug"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}  # Removed empty string
