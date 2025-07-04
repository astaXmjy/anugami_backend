# categories/views.py - Modified to disable pagination on main endpoint

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils import timezone
from .models import Category, CategoryImage, CategorySEO, CategoryRequest
from .serializers import (
    CategoryDetailSerializer,
    CategoryListSerializer,
    CategoryTreeSerializer,
    CategoryImageSerializer,
    CategoryMoveSerializer,
    CategoryBulkActionSerializer,
    CategoryRequestSerializer,
)
from .services import CategoryService
from system_users.permissions import HasModulePermission
import logging

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing categories with tree structure support
    """

    serializer_class = CategoryDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, FileUploadParser]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "is_active": ["exact"],
        "is_featured": ["exact"],
        "parent": ["exact", "isnull"],
        "created_at": ["gte", "lte"],
    }
    search_fields = ["name", "description", "meta_keywords"]
    ordering_fields = ["name", "created_at", "menu_order", "product_count"]
    lookup_field = "slug"

    # Set pagination_class to None to disable pagination
    pagination_class = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_service = CategoryService()

    def get_queryset(self):
        """
        Get base queryset with proper joins and filters
        """
        queryset = Category.objects.select_related(
            "parent", "seo", "created_by", "updated_by"
        ).prefetch_related("images", "attributes", "children")

        # Apply user-based filtering
        user = self.request.user
        if not user.is_authenticated or not (
            user.is_superuser or (hasattr(user, "is_admin") and user.is_admin)
        ):
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action
        """
        if self.action == "list":
            return CategoryListSerializer
        if self.action == "tree":
            return CategoryTreeSerializer
        return CategoryDetailSerializer

    def list(self, request, *args, **kwargs):
        """
        Override list method to handle pagination disabling and add caching
        """
        try:
            # Check for cached response
            cache_key = "all_categories"
            cached_data = cache.get(cache_key)

            if cached_data:
                logger.info("Returning all categories from cache")
                return Response(cached_data)

            # Get filtered queryset
            queryset = self.filter_queryset(self.get_queryset())

            # Serialize data
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data

            # Create response in same format as paginated response
            result = {
                "count": len(data),
                "next": None,
                "previous": None,
                "results": data,
            }

            # Cache the response
            cache.set(cache_key, result, 300)  # Cache for 5 minutes

            logger.info(f"Retrieved all {len(data)} categories at once")
            return Response(result)
        except Exception as e:
            logger.error(f"Error fetching all categories: {str(e)}")
            return Response(
                {"error": "Failed to fetch categories: " + str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def perform_create(self, serializer):
        """
        Create category with user tracking
        """
        try:
            category = serializer.save(
                created_by=self.request.user,
                updated_by=self.request.user,
                slug=slugify(serializer.validated_data["name"]),
            )
            # Clear cache when categories are modified
            cache.delete("all_categories")
            cache.delete("category_tree")
            logger.info(
                f"Category created: {category.name} by {self.request.user.email}"
            )
        except Exception as e:
            logger.error(f"Category creation failed: {str(e)}")
            raise

    def perform_update(self, serializer):
        """
        Update category with user tracking
        """
        try:
            category = serializer.save(updated_by=self.request.user)
            # Clear cache when categories are modified
            cache.delete("all_categories")
            cache.delete("category_tree")
            logger.info(
                f"Category updated: {category.name} by {self.request.user.email}"
            )
        except Exception as e:
            logger.error(f"Category update failed: {str(e)}")
            raise

    def perform_destroy(self, instance):
        """
        Delete category with validation and cleanup
        """
        if instance.children.exists():
            raise ValidationError("Cannot delete category with child categories")
        try:
            name = instance.name
            instance.delete()
            # Clear cache when categories are modified
            cache.delete("all_categories")
            cache.delete("category_tree")
            logger.info(f"Category deleted: {name} by {self.request.user.email}")
        except Exception as e:
            logger.error(f"Category deletion failed: {str(e)}")
            raise

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """
        Get complete category tree
        """
        try:
            # Try to get from cache
            cache_key = "category_tree"
            tree_data = cache.get(cache_key)

            if not tree_data:
                # Build tree from database
                root_nodes = (
                    self.get_queryset()
                    .filter(parent__isnull=True)
                    .order_by("menu_order")
                )
                serializer = CategoryTreeSerializer(root_nodes, many=True)
                tree_data = serializer.data

                # Cache for 1 hour
                cache.set(cache_key, tree_data, 3600)

            return Response(tree_data)
        except Exception as e:
            logger.error(f"Error fetching category tree: {str(e)}")
            return Response(
                {"error": "Failed to fetch category tree"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def move(self, request, slug=None):
        """
        Move category in the tree structure
        """
        category = self.get_object()
        serializer = CategoryMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            target = Category.objects.get(id=serializer.validated_data["target_id"])
            position = serializer.validated_data["position"]

            # Validate move operation
            if target == category:
                raise ValidationError("Cannot move category to itself")
            if target.is_descendant_of(category):
                raise ValidationError("Cannot move category to its own descendant")

            # Perform move
            category.move_to(target, position)

            # Clear cache
            cache.delete("category_tree")
            cache.delete("all_categories")

            logger.info(
                f"Category moved: {category.name} to {position} of {target.name}"
            )
            return Response({"status": "success"})
        except Category.DoesNotExist:
            return Response(
                {"error": "Target category not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Category move failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def upload_image(self, request, slug=None):
        """
        Upload category image
        """
        category = self.get_object()
        image_file = request.FILES.get("image")
        is_primary = request.data.get("is_primary", False)

        if not image_file:
            return Response(
                {"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Upload and optimize image
            image_data = self.category_service.handle_category_image(
                str(category.id), image_file, "medium" if is_primary else "gallery"
            )

            if not image_data:
                return Response(
                    {"error": "Failed to upload image"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Create image record
            image = CategoryImage.objects.create(
                category=category,
                image_url=image_data["url"],
                alt_text=request.data.get("alt_text", ""),
                is_primary=is_primary,
                sort_order=request.data.get("sort_order", 0),
                width=image_data["metadata"]["width"],
                height=image_data["metadata"]["height"],
                file_size=image_data["metadata"]["file_size"],
            )

            # Handle primary image logic
            if is_primary:
                CategoryImage.objects.filter(
                    category=category, is_primary=True
                ).exclude(id=image.id).update(is_primary=False)

            # Clear cache
            cache.delete("all_categories")

            return Response(
                CategoryImageSerializer(image).data, status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Image upload failed: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["delete"])
    def delete_image(self, request, slug=None, image_id=None):
        """
        Delete category image
        """
        category = self.get_object()
        image = get_object_or_404(CategoryImage, id=image_id, category=category)

        try:
            if self.category_service.delete_category_image(image.image_url):
                image.delete()
                # Clear cache
                cache.delete("all_categories")
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"error": "Failed to delete image"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Image deletion failed: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"])
    def bulk_action(self, request):
        """
        Perform bulk actions on categories
        """
        serializer = CategoryBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            action = serializer.validated_data["action"]
            category_ids = serializer.validated_data["ids"]
            categories = Category.objects.filter(id__in=category_ids)

            if action == "activate":
                categories.update(is_active=True)
            elif action == "deactivate":
                categories.update(is_active=False)
            elif action == "delete":
                # Check for children
                if Category.objects.filter(parent__in=categories).exists():
                    raise ValidationError("Cannot delete categories with children")
                categories.delete()
            elif action == "move":
                target_id = serializer.validated_data.get("target_id")
                position = serializer.validated_data.get("position")
                if not (target_id and position):
                    raise ValidationError(
                        "target_id and position required for move action"
                    )

                target = Category.objects.get(id=target_id)
                for category in categories:
                    if target != category and not target.is_descendant_of(category):
                        category.move_to(target, position)

            # Clear cache
            cache.delete("category_tree")
            cache.delete("all_categories")

            return Response({"status": "success"})
        except Exception as e:
            logger.error(f"Bulk action failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def descendants(self, request, slug=None):
        """
        Get all descendants of a category
        """
        category = self.get_object()
        descendants = category.get_descendants(include_self=False)
        serializer = CategoryListSerializer(descendants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def ancestors(self, request, slug=None):
        """
        Get all ancestors of a category
        """
        category = self.get_object()
        ancestors = category.get_ancestors(include_self=False)
        serializer = CategoryListSerializer(ancestors, many=True)
        return Response(serializer.data)


class CategoryRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing category requests from sellers to admins
    """

    serializer_class = CategoryRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "requested_by__email"]
    ordering_fields = ["created_at", "name", "status"]

    def get_queryset(self):
        """
        Get queryset based on user role:
        - Admins can see all requests
        - Sellers can only see their own requests
        """
        user = self.request.user

        if user.is_superuser or (hasattr(user, "is_admin") and user.is_admin):
            return CategoryRequest.objects.all()

        # For sellers and other users, only show their own requests
        return CategoryRequest.objects.filter(requested_by=user)

    def perform_create(self, serializer):
        """
        Set requested_by to current user when creating a request
        """
        serializer.save(requested_by=self.request.user)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, HasModulePermission],
    )
    def approve(self, request, pk=None):
        """
        Approve a category request and create the actual category
        """
        category_request = self.get_object()

        # Check if request is already processed
        if category_request.status != "pending":
            return Response(
                {"error": f"Request already {category_request.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create the new category
        parent = category_request.parent

        try:
            from .services import CategoryService

            service = CategoryService()

            # Generate a unique slug
            slug = service.generate_unique_slug(category_request.name)

            # Create the category
            category = Category.objects.create(
                name=category_request.name,
                slug=slug,
                description=category_request.description,
                parent=parent,
                created_by=request.user,
                updated_by=request.user,
            )

            # Update the request
            category_request.status = "approved"
            category_request.reviewed_by = request.user
            category_request.reviewed_at = timezone.now()
            category_request.admin_notes = request.data.get("admin_notes", "")
            category_request.save()

            # Clear cache
            cache.delete("category_tree")
            cache.delete("all_categories")

            # Return the newly created category and updated request
            from .serializers import CategoryDetailSerializer

            category_serializer = CategoryDetailSerializer(category)
            request_serializer = self.get_serializer(category_request)

            return Response(
                {
                    "message": "Category request approved",
                    "category": category_serializer.data,
                    "request": request_serializer.data,
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to create category: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, HasModulePermission],
    )
    def reject(self, request, pk=None):
        """
        Reject a category request
        """
        category_request = self.get_object()

        # Check if request is already processed
        if category_request.status != "pending":
            return Response(
                {"error": f"Request already {category_request.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update the request
        category_request.status = "rejected"
        category_request.reviewed_by = request.user
        category_request.reviewed_at = timezone.now()
        category_request.admin_notes = request.data.get("admin_notes", "")
        category_request.save()

        return Response(
            {
                "message": "Category request rejected",
                "request": self.get_serializer(category_request).data,
            }
        )
