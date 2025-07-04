from rest_framework import serializers
from django.utils.text import slugify
from .models import BlogPost, BlogCategory, BlogImage, BlogComment, BlogTag


class BlogCategorySerializer(serializers.ModelSerializer):
    """Serializer for Blog Category"""

    class Meta:
        model = BlogCategory
        fields = ["id", "name", "slug", "description", "is_active", "created_at"]
        read_only_fields = ["id", "slug", "created_at"]

    def create(self, validated_data):
        """Ensure slug is created from name"""
        if not validated_data.get("slug"):
            validated_data["slug"] = slugify(validated_data["name"])
        return super().create(validated_data)


class BlogImageSerializer(serializers.ModelSerializer):
    """Serializer for Blog Images"""

    class Meta:
        model = BlogImage
        fields = [
            "id",
            "blog_post",
            "image_url",
            "storage_path",
            "alt_text",
            "caption",
            "sort_order",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BlogTagSerializer(serializers.ModelSerializer):
    """Serializer for Blog Tags"""

    class Meta:
        model = BlogTag
        fields = ["id", "name", "slug"]
        read_only_fields = ["id", "slug"]


class BlogCommentSerializer(serializers.ModelSerializer):
    """Serializer for Blog Comments"""

    author_name = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = BlogComment
        fields = [
            "id",
            "blog_post",
            "parent",
            "author",
            "author_name",
            "content",
            "is_approved",
            "created_at",
            "replies",
        ]
        read_only_fields = ["id", "is_approved", "created_at"]

    def get_author_name(self, obj):
        return obj.author.name if obj.author else "Anonymous"

    def get_replies(self, obj):
        if obj.replies.exists():
            return BlogCommentSerializer(obj.replies.all(), many=True).data
        return []


class BlogPostListSerializer(serializers.ModelSerializer):
    """Enhanced List serializer for Blog Posts with category details"""

    category = BlogCategorySerializer(
        read_only=True
    )  # Full category details instead of just name
    author_name = serializers.CharField(source="author.name", read_only=True)
    tags = BlogTagSerializer(many=True, read_only=True)
    # Add excerpt and content for preview purposes
    excerpt_preview = serializers.SerializerMethodField()
    content_preview = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "excerpt_preview",
            "content_preview",
            "featured_image_url",
            "category",  # Now includes full category with description
            "author_name",
            "status",
            "is_featured",
            "views_count",
            "tags",
            "published_at",
            "created_at",
            # Add meta fields for SEO
            "meta_title",
            "meta_description",
            "meta_keywords",
        ]
        read_only_fields = ["id", "slug", "views_count", "created_at"]

    def get_excerpt_preview(self, obj):
        """Get a clean text preview of excerpt"""
        if obj.excerpt:
            # Remove HTML tags for preview
            import re

            clean_text = re.sub(r"<[^>]+>", "", obj.excerpt)
            return clean_text[:200] + "..." if len(clean_text) > 200 else clean_text
        return ""

    def get_content_preview(self, obj):
        """Get a clean text preview of content"""
        if obj.content:
            # Remove HTML tags for preview
            import re

            clean_text = re.sub(r"<[^>]+>", "", obj.content)
            return clean_text[:300] + "..." if len(clean_text) > 300 else clean_text
        return ""


class BlogPostDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Blog Posts"""

    category = BlogCategorySerializer(read_only=True)
    author_name = serializers.CharField(source="author.name", read_only=True)
    images = BlogImageSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    tags = BlogTagSerializer(many=True, read_only=True)

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "slug",
            "content",
            "excerpt",
            "category",
            "author_name",
            "featured_image_url",
            "status",
            "is_featured",
            "views_count",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "images",
            "comments",
            "tags",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "views_count", "created_at", "updated_at"]

    def get_comments(self, obj):
        """Get approved top-level comments"""
        comments = obj.comments.filter(parent=None, is_approved=True).order_by(
            "-created_at"
        )
        return BlogCommentSerializer(comments, many=True).data


class BlogPostCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating Blog Posts"""

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=BlogCategory.objects.all(), source="category"
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=BlogTag.objects.all(), many=True, required=False, source="tags"
    )

    class Meta:
        model = BlogPost
        fields = [
            "title",
            "content",
            "excerpt",
            "category_id",
            "featured_image_url",
            "status",
            "is_featured",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "tag_ids",
            "published_at",
        ]

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        blog_post = super().create(validated_data)
        blog_post.tags.set(tags)
        return blog_post

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        blog_post = super().update(instance, validated_data)
        if tags is not None:
            blog_post.tags.set(tags)
        return blog_post
