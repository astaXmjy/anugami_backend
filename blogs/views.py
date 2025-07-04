from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django.db.models import Q
from django.core.cache import cache
from django.utils.timezone import now

from .models import BlogPost, BlogCategory, BlogComment, BlogTag
from .serializers import (
    BlogPostListSerializer,
    BlogPostDetailSerializer,
    BlogPostCreateUpdateSerializer,
    BlogCategorySerializer,
    BlogCommentSerializer,
    BlogTagSerializer,
)
from .services import BlogService, BlogCommentService
from .constants import BLOG_CACHE_KEY, CACHE_TIMEOUT
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import BlogImageService
import uuid


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_ckeditor_image(request):
    """Handle CKEditor image upload"""
    if "upload" not in request.FILES:
        return Response({"error": {"message": "No image file provided"}})

    try:
        image_service = BlogImageService()
        file = request.FILES["upload"]

        # Generate a unique folder name for CKEditor images
        unique_folder = f"blog_content_{uuid.uuid4().hex[:8]}"

        # Upload to Firebase
        file_path, file_url = image_service.upload_image(
            file=file, blog_id=unique_folder
        )

        return Response({"url": file_url, "storage_path": file_path})

    except Exception as e:
        return Response({"error": {"message": str(e)}})


class BlogPostViewSet(viewsets.ModelViewSet):
    """ViewSet for managing blog posts"""

    queryset = BlogPost.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "content", "excerpt", "meta_keywords"]
    ordering_fields = ["created_at", "views_count", "title"]
    lookup_field = "slug"
    blog_service = BlogService()

    def get_queryset(self):
        """Customize queryset based on user and filters"""
        queryset = super().get_queryset()

        # If not staff/author, show only published posts
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(status="published") & Q(published_at__lte=now())
            )

        # Category filter
        category_slug = self.request.query_params.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Tag filter
        tag_slug = self.request.query_params.get("tag")
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)

        # Author filter
        author_id = self.request.query_params.get("author")
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        return queryset.select_related("category", "author").prefetch_related(
            "tags", "images"
        )

    def get_serializer_class(self):
        """Select appropriate serializer based on action"""
        if self.action == "list":
            return BlogPostListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return BlogPostCreateUpdateSerializer
        return BlogPostDetailSerializer

    def get_object(self):
        """Get blog post and increment view count"""
        obj = super().get_object()
        if self.action == "retrieve":
            self.blog_service.increment_view_count(obj)
        return obj

    def perform_create(self, serializer):
        """Set author and handle image upload when creating post"""
        blog_post = self.blog_service.create_blog_post(
            data=serializer.validated_data, author=self.request.user
        )
        serializer.instance = blog_post

    def perform_update(self, serializer):
        """Handle image update when updating post"""
        blog_post = self.blog_service.update_blog_post(
            blog_post=serializer.instance,
            data=serializer.validated_data,
            user=self.request.user,
        )
        serializer.instance = blog_post

    def perform_destroy(self, instance):
        """Delete blog post and associated images"""
        self.blog_service.delete_blog_post(instance)

    @action(detail=False, methods=["GET"])
    def featured(self, request):
        """Get featured blog posts"""
        featured_posts = self.get_queryset().filter(is_featured=True)[:5]
        serializer = BlogPostListSerializer(featured_posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def trending(self, request):
        """Get trending posts based on views"""
        trending_posts = self.get_queryset().order_by("-views_count")[:5]
        serializer = BlogPostListSerializer(trending_posts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def add_comment(self, request, slug=None):
        """Add a comment to a blog post"""
        blog_post = self.get_object()
        parent_id = request.data.get("parent_id")
        content = request.data.get("content")

        if not content:
            return Response(
                {"error": "Comment content is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parent_comment = None
            if parent_id:
                parent_comment = BlogComment.objects.get(id=parent_id)

            comment = BlogCommentService.add_comment(
                blog_post=blog_post,
                author=request.user,
                content=content,
                parent_comment=parent_comment,
            )
            serializer = BlogCommentSerializer(comment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Parent comment not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BlogCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for blog categories"""

    queryset = BlogCategory.objects.all()
    serializer_class = BlogCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def get_queryset(self):
        """Filter active categories for non-staff users"""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset


class BlogCommentViewSet(viewsets.ModelViewSet):
    """ViewSet for blog comments"""

    queryset = BlogComment.objects.all()
    serializer_class = BlogCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter comments based on user role"""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(author=self.request.user) | Q(is_approved=True)
            )
        return queryset.select_related("blog_post", "author", "parent")

    @action(detail=True, methods=["POST"])
    def approve(self, request, pk=None):
        """Approve a comment"""
        if not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        comment = self.get_object()
        success = BlogCommentService.approve_comment(comment)

        if success:
            return Response({"message": "Comment approved successfully"})
        return Response(
            {"error": "Failed to approve comment"}, status=status.HTTP_400_BAD_REQUEST
        )


class BlogTagViewSet(viewsets.ModelViewSet):
    """ViewSet for blog tags"""

    queryset = BlogTag.objects.all()
    serializer_class = BlogTagSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    @action(detail=True, methods=["GET"])
    def posts(self, request, slug=None):
        """Get posts for a specific tag"""
        tag = self.get_object()
        print(tag)
        posts = tag.blog_posts.filter(
            status="published", published_at__lte=now()
        ).order_by("-created_at")

        serializer = BlogPostListSerializer(posts, many=True)
        return Response(serializer.data)
