# mine old
# Combined implementation for Product views
import os
import uuid
import time
import re
import logging
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets, status, filters, permissions, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    AllowAny,
)
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.views import APIView
import csv
from decimal import Decimal
from io import TextIOWrapper
from django.http import HttpResponse
from django.db import transaction, connection
from django.db.models import Q, Avg, Value, F
from django.db.models.functions import Replace
from django.core.cache import cache
import logging
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from datetime import datetime

from .models import (
    Product,
    ProductReview,
    ProductStock,
    ProductImage,
    ProductVideo,
    Brand,
    ProductVariant,
    VariantAttribute,
    ProductFeatureRequest,
    ProductAttribute,
)
from .serializers import (
    ProductSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductReviewSerializer,
    ProductImageSerializer,
    ProductVideoSerializer,
    ProductAvailabilitySerializer,
    ProductStockAlertSerializer,
    BrandSerializer,
    ProductVariantSerializer,
    ProductVariantDetailSerializer,
    ProductAttributeSerializer,
    ProductFeatureRequestSerializer,
    SellerInfoSerializer,
    ProductVariantSerializer,
)

from .services import ImageService, VideoService
from categories.models import Category
from system_users.permissions import HasModulePermission

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    """
    Comprehensive Multi-Vendor Product Management Viewset
    """

    queryset = Product.objects.all()
    permission_classes = [IsAuthenticated, HasModulePermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "sku", "brand__name"]
    ordering_fields = ["created_at", "name", "regular_price", "stock_quantity"]
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in [
            "list",
            "retrieve",
            "featured",
            "by_category_tree",
            "search",
            "variants",
            "variant_matrix",
            "color_images",
            "available_options",
            "check_variant_availability",
            "mobile_variant_selector",  # Added missing action
            "variant_detail",  # Added missing action
            "track_product_view",  # Added missing action
            "recently_viewed",  # Added missing action
            "complementary_products",  # Added missing action
        ]:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, HasModulePermission]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """
        Customize queryset for multi-vendor context:
        - Admins/superusers see ALL products regardless of status
        - Sellers see only THEIR OWN products (including draft/featured)
        - Anonymous/other users see only active published products
        """
        queryset = super().get_queryset()
        user = self.request.user

        # Anonymous users can only see active/published products
        if not user.is_authenticated:
            return queryset.filter(is_active=True, status="published")

        # Superusers and admins can see all products
        if user.is_superuser or (hasattr(user, "is_admin") and user.is_admin):
            return queryset

        # Users with products.read permission can see all products
        if hasattr(user, "has_module_permission") and user.has_module_permission(
            "products", "read"
        ):
            return queryset

        # Sellers can see all their own products (including drafts)
        return queryset.filter(seller=user)

    def get_serializer_class(self):
        """
        Dynamic serializer selection
        """
        if self.action == "list":
            return ProductListSerializer
        elif self.action in [
            "retrieve",
            "create",
            "update",
            "partial_update",
            "create_product",
        ]:
            return ProductDetailSerializer
        return ProductSerializer

    def list(self, request, *args, **kwargs):
        """
        Override list method to handle no_page parameter for disabling pagination
        """
        queryset = self.filter_queryset(self.get_queryset())
        no_page = request.query_params.get("no_page", "false").lower() == "true"

        if no_page:
            # Return all products without pagination
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        else:
            # Use default pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

    def perform_create(self, serializer):
        # Ensure brand_id is provided in the request data
        brand_id = self.request.data.get("brand")
        if not brand_id:
            raise serializers.ValidationError({"brand": "This field is required."})

        # Check if the brand exists
        try:
            brand = Brand.objects.get(id=brand_id)
        except Brand.DoesNotExist:
            raise serializers.ValidationError({"brand": "Brand does not exist."})

        # Ensure category_id is provided in the request data
        category_id = self.request.data.get("category")
        if not category_id:
            raise serializers.ValidationError({"category": "This field is required."})

        # Check if the category exists
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            raise serializers.ValidationError({"category": "Category does not exist."})

        # Set the seller, brand, and category before saving the product
        serializer.save(seller=self.request.user, brand=brand, category=category)

    @action(detail=False, methods=["POST"], url_path="create-product")
    def create_product(self, request):
        """
        Custom endpoint for creating a product.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(detail=False, methods=["GET"])
    def seller_products(self, request):
        """
        Get products for the current seller
        """
        if request.user.is_anonymous:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        products = self.get_queryset().filter(seller=request.user)

        # Handle no_page parameter
        no_page = request.query_params.get("no_page", "false").lower() == "true"
        if no_page:
            serializer = self.get_serializer(products, many=True)
            return Response(serializer.data)

        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    def variants(self, request, slug=None):
        """
        Get all variants for a specific product
        """
        product = self.get_object()
        variants = ProductVariant.objects.filter(product=product)

        # Apply additional filters if provided
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            is_active = is_active.lower() == "true"
            variants = variants.filter(is_active=is_active)

        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def create_variant(self, request, slug=None):
        """Creates a new variant for a product."""
        product = self.get_object()

        # Check permissions
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        # Create variant with basic data
        variant_data = {
            "product": product.id,
            "sku": request.data.get("sku"),
            "stock_quantity": request.data.get("stock_quantity", 0),
            "price_adjustment": request.data.get("price_adjustment", 0),
            "is_active": request.data.get("is_active", True),
        }

        # Handle custom price if provided
        if "custom_price" in request.data and request.data.get("custom_price"):
            variant_data["has_custom_price"] = True
            variant_data["custom_price"] = request.data.get("custom_price")

        serializer = ProductVariantDetailSerializer(data=variant_data)
        if serializer.is_valid():
            variant = serializer.save()

            # Process attributes with prices
            attributes = request.data.get("attributes", [])
            for attr in attributes:
                VariantAttribute.objects.create(
                    variant=variant,
                    attribute_type=attr.get("attribute_type"),
                    value=attr.get("value"),
                    display_value=attr.get("display_value", None),
                )

            return Response(
                ProductVariantDetailSerializer(variant).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["POST"])
    def bulk_create_variants(self, request, slug=None):
        """Creates multiple variants for a product at once."""
        product = self.get_object()

        # Check permissions
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        variants_data = request.data.get("variants", [])
        if not variants_data:
            return Response(
                {"error": "No variant data provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_variants = []
        errors = []

        with transaction.atomic():
            for variant_data in variants_data:
                try:
                    # Prepare basic variant data
                    serializer_data = {
                        "product": product.id,
                        "sku": variant_data.get("sku"),
                        "stock_quantity": variant_data.get("stock_quantity", 0),
                        "price_adjustment": variant_data.get("price_adjustment", 0),
                        "is_active": variant_data.get("is_active", True),
                    }

                    # Handle custom price if provided
                    if "custom_price" in variant_data and variant_data.get(
                        "custom_price"
                    ):
                        serializer_data["has_custom_price"] = True
                        serializer_data["custom_price"] = variant_data.get(
                            "custom_price"
                        )

                    # Create the variant
                    serializer = ProductVariantDetailSerializer(data=serializer_data)
                    if serializer.is_valid():
                        variant = serializer.save()

                        # Process attributes with prices
                        attributes = variant_data.get("attributes", [])
                        for attr in attributes:
                            VariantAttribute.objects.create(
                                variant=variant,
                                attribute_type=attr.get("attribute_type"),
                                value=attr.get("value"),
                                display_value=attr.get("display_value", None),
                            )

                        created_variants.append(
                            ProductVariantDetailSerializer(variant).data
                        )
                    else:
                        errors.append(
                            {"data": serializer_data, "errors": serializer.errors}
                        )
                        raise ValidationError(f"Validation error: {serializer.errors}")

                except Exception as e:
                    errors.append({"data": variant_data, "error": str(e)})
                    raise

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": f"Successfully created {len(created_variants)} variants",
                "variants": created_variants,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["GET"])
    def featured(self, request):
        """
        Get featured products across all vendors
        """
        featured_products = self.get_queryset().filter(
            is_featured=True, is_active=True, status="published"
        )

        # Handle no_page parameter
        no_page = request.query_params.get("no_page", "false").lower() == "true"
        if no_page:
            serializer = self.get_serializer(featured_products, many=True)
            return Response(serializer.data)

        page = self.paginate_queryset(featured_products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(featured_products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    def availability(self, request, slug=None):
        """
        Check product availability with vendor-specific logic
        """
        product = get_object_or_404(Product, slug=slug)

        data = {
            "product": product,
            "is_available": (
                product.is_active
                and product.status == "published"
                and product.stock_quantity > 0
            ),
            "available_quantity": product.stock_quantity,
            "can_backorder": product.allow_backorder,
            "estimated_restock_date": None,  # Future implementation
        }

        serializer = ProductAvailabilitySerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    def stock_alert(self, request, slug=None):
        """
        Check stock alert status for vendor
        """
        product = get_object_or_404(Product, slug=slug)

        # Ensure only seller or staff can view stock alerts
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        data = {
            "product": product,
            "current_stock": product.stock_quantity,
            "low_stock_threshold": product.low_stock_threshold,
            "is_low_stock": product.stock_quantity <= product.low_stock_threshold,
        }

        serializer = ProductStockAlertSerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def upload_images(self, request, slug=None):
        """
        Upload multiple product images with unique identifiers for each image
        """
        product = get_object_or_404(Product, slug=slug)

        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        images = request.FILES.getlist("images")
        if not images:
            return Response(
                {"error": "No images provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(
            f"Received {len(images)} images for product {product.id} ({product.name})"
        )

        image_service = ImageService()
        uploaded_images = []

        # Track whether this is the first image (to potentially set as primary)
        should_set_primary = request.data.get("is_primary") == "true"
        is_first_image = True

        for index, image in enumerate(images):
            try:
                # Extract original filename if available
                original_filename = ""
                if hasattr(image, "name"):
                    original_filename = os.path.splitext(image.name)[0]
                    original_filename = re.sub(r"[^a-zA-Z0-9_]", "_", original_filename)

                # Generate a unique identifier for each image
                unique_id = uuid.uuid4().hex[:8]
                timestamp = int(time.time())

                # Create a unique name for each image that includes:
                # - Original filename (if available)
                # - Index in batch
                # - Unique ID
                # - Timestamp
                custom_name = f"{product.name}_{original_filename if original_filename else 'image'}_{index+1}_{timestamp}_{unique_id}"

                logger.info(f"Processing image {index+1}/{len(images)}: {custom_name}")

                # Upload with unique identifier
                file_path, file_url = image_service.upload_image(
                    image, str(product.id), custom_name
                )

                # Determine if this image should be primary
                is_primary = should_set_primary and is_first_image

                image_serializer = ProductImageSerializer(
                    data={
                        "product": product.id,
                        "image_url": file_url,
                        "storage_path": file_path,
                        "alt_text": request.data.get("alt_text", ""),
                        "is_primary": is_primary,
                    }
                )

                if image_serializer.is_valid():
                    image_obj = image_serializer.save()
                    uploaded_images.append(image_serializer.data)

                    # If this was the first image and set as primary, update flag
                    if is_primary:
                        is_first_image = False

                    logger.info(
                        f"Successfully saved image {index+1} with ID {image_obj.id}"
                    )
                else:
                    logger.error(
                        f"Image serializer validation failed: {image_serializer.errors}"
                    )
                    return Response(
                        image_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                logger.error(f"Error uploading image {index+1}: {str(e)}")
                return Response(
                    {"error": f"Failed to upload image: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "message": f"Successfully uploaded {len(uploaded_images)} images",
                "images": uploaded_images,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["DELETE"])
    def delete_image(self, request, slug=None):
        product = get_object_or_404(Product, slug=slug)

        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        image_id = request.data.get("image_id")
        if not image_id:
            return Response(
                {"error": "Image ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            image = ProductImage.objects.get(id=int(image_id), product=product)
        except ProductImage.DoesNotExist:
            return Response(
                {"error": "Image not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Delete the image from Firebase Storage
        image_service = ImageService()
        if image_service.delete_image(image.storage_path):
            image.delete()  # Delete the image record from the database
            return Response(
                {"message": "Image deleted successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Failed to delete image from Firebase"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["DELETE"])
    def delete_all_images(self, request, slug=None):
        product = get_object_or_404(Product, slug=slug)
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        images = product.images.all()
        if not images:
            return Response(
                {"message": "No images found for this product"},
                status=status.HTTP_200_OK,
            )
        image_service = ImageService()
        deleted_count = 0
        for image in images:
            if image_service.delete_image(image.storage_path):
                image.delete()  # Delete the image record from the database
                deleted_count += 1

        return Response(
            {"message": f"{deleted_count} images deleted successfully"},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["POST"])
    def upload_videos(self, request, slug=None):
        product = get_object_or_404(Product, slug=slug)
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        videos = request.FILES.getlist("videos")
        if not videos:
            return Response(
                {"error": "No videos provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        video_service = VideoService()
        uploaded_videos = []

        for video in videos:
            try:
                file_path, file_url = video_service.upload_video(video, str(product.id))
                video_serializer = ProductVideoSerializer(
                    data={
                        "product": product.id,
                        "video_url": file_url,
                        "storage_path": file_path,
                        "title": request.data.get("title", ""),
                    }
                )
                if video_serializer.is_valid():
                    video_obj = video_serializer.save()
                    uploaded_videos.append(video_serializer.data)
                else:
                    return Response(
                        video_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                return Response(
                    {"error": f"Failed to upload video: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(uploaded_videos, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["DELETE"])
    def delete_video(self, request, slug=None):
        """Delete a specific video"""
        product = get_object_or_404(Product, slug=slug)

        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        video_id = request.data.get("video_id")
        if not video_id:
            return Response(
                {"error": "Video ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            video = ProductVideo.objects.get(id=int(video_id), product=product)
        except ProductVideo.DoesNotExist:
            return Response(
                {"error": "Video not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Delete from Firebase Storage
        video_service = VideoService()
        if video_service.delete_video(video.storage_path):
            video.delete()  # Delete from database
            return Response(
                {"message": "Video deleted successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Failed to delete video from Firebase"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    def set_featured_video(self, request, slug=None):
        """Set a video as featured"""
        product = get_object_or_404(Product, slug=slug)

        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        video_id = request.data.get("video_id")
        if not video_id:
            return Response(
                {"error": "Video ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            video = ProductVideo.objects.get(id=int(video_id), product=product)
        except ProductVideo.DoesNotExist:
            return Response(
                {"error": "Video not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # First, remove featured status from all other videos of this product
        ProductVideo.objects.filter(product=product).update(is_featured=False)

        # Set this video as featured
        video.is_featured = True
        video.save()

        return Response(
            {"message": "Video set as featured successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["POST"])
    def update_attributes(self, request, slug=None):
        """Update attributes for a product"""
        product = self.get_object()

        # Permission check
        if not (request.user.is_staff or request.user == product.seller):
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        attributes_data = request.data.get("attributes", [])

        try:
            with transaction.atomic():
                # Clear existing attributes
                product.attributes.all().delete()

                # Create new attributes
                for attr_data in attributes_data:
                    # Skip empty attributes
                    if not attr_data.get("name") or not attr_data.get("value"):
                        continue

                    ProductAttribute.objects.create(
                        product=product,
                        attribute_type=attr_data.get("attribute_type", "custom"),
                        name=attr_data.get("name"),
                        value=attr_data.get("value"),
                        display_value=attr_data.get("display_value")
                        or attr_data.get("value"),
                        type=attr_data.get("type", "text"),
                        is_visible=attr_data.get("is_visible", True),
                        is_variation=attr_data.get("is_variation", False),
                        is_searchable=attr_data.get("is_searchable", True),
                        sort_order=int(attr_data.get("sort_order", 0)),
                    )

            # Return updated product
            product_serializer = ProductDetailSerializer(product)
            return Response(product_serializer.data)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["GET"])
    def by_category_tree(self, request):
        """
        Get products for a category and all its descendants
        """
        category_slug = request.query_params.get("slug")
        if not category_slug:
            return Response(
                {"error": "Category slug is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get the category and all its descendants
            from categories.models import Category

            category = Category.objects.get(slug=category_slug)
            descendant_categories = list(category.get_descendants(include_self=True))

            # Filter products by the category and all its descendants
            products = self.get_queryset().filter(category__in=descendant_categories)

            # Apply additional filters if needed
            is_active = request.query_params.get("is_active")
            if is_active is not None:
                is_active = is_active.lower() == "true"
                products = products.filter(is_active=is_active)

            status_filter = request.query_params.get("status")
            if status_filter:
                products = products.filter(status=status_filter)

            # Handle no_page parameter for disabling pagination
            no_page = request.query_params.get("no_page", "false").lower() == "true"
            if no_page:
                serializer = self.get_serializer(products, many=True)
                return Response(serializer.data)

            # Paginate results if needed
            page = self.paginate_queryset(products)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(products, many=True)
            return Response(serializer.data)
        except Category.DoesNotExist:
            return Response(
                {"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["POST"])
    def assign_shipping_policy(self, request, slug=None):
        """Assign a shipping policy to a product"""
        product = self.get_object()

        # Check if user has permission
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        # Get policy ID from request
        policy_id = request.data.get("policy_id")
        if not policy_id:
            return Response(
                {"error": "Shipping policy ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Import here to avoid circular imports
            from sellers.models import ShippingPolicy
            from sellers.serializers import ShippingPolicySerializer

            # Get the policy
            policy = ShippingPolicy.objects.get(id=policy_id)

            # Check if policy belongs to the product's seller
            if policy.seller != product.seller.seller_profile:
                return Response(
                    {"error": "You can only use your own shipping policies"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Assign policy to product
            product.shipping_policy_id = str(policy_id)

            # Cache the policy data (serialized)
            policy_serializer = ShippingPolicySerializer(policy)
            product.shipping_policy_data = policy_serializer.data

            product.save()

            return Response(
                {
                    "message": "Shipping policy assigned successfully",
                    "product": product.name,
                    "policy": policy.title,
                }
            )

        except ShippingPolicy.DoesNotExist:
            return Response(
                {"error": "Shipping policy not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["POST"])
    def bulk_assign_shipping_policy(self, request):
        """Assign a shipping policy to multiple products"""
        user = request.user

        # Get policy ID and product IDs from request
        policy_id = request.data.get("policy_id")
        product_ids = request.data.get("product_ids", [])

        if not policy_id or not product_ids:
            return Response(
                {"error": "Shipping policy ID and product IDs are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Import here to avoid circular imports
            from shipping_policies.models import ShippingPolicy
            from shipping_policies.serializers import ShippingPolicySerializer

            # Get the policy
            policy = ShippingPolicy.objects.get(id=policy_id)

            # For non-admin users, only allow them to use their own policies
            if not user.is_staff:
                if not hasattr(user, "seller") or policy.seller != user.seller:
                    return Response(
                        {"error": "You can only use your own shipping policies"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Get products and check permissions
            products = self.get_queryset().filter(id__in=product_ids)

            # For non-admin users, filter to just their products
            if not user.is_staff:
                products = products.filter(seller=user)

            if not products:
                return Response(
                    {"error": "No valid products found for update"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Cache the policy data
            policy_data = ShippingPolicySerializer(policy).data

            # Update all products
            updated_count = 0
            for product in products:
                product.shipping_policy_id = str(policy_id)
                product.shipping_policy_data = policy_data
                product.save()
                updated_count += 1

            return Response(
                {
                    "message": f"Shipping policy assigned to {updated_count} products",
                    "policy": policy.title,
                }
            )

        except ShippingPolicy.DoesNotExist:
            return Response(
                {"error": "Shipping policy not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["GET"])
    def search(self, request):
        """Search products with advanced filtering"""
        queryset = self.filter_queryset(self.get_queryset())

        # Apply search filters
        search_query = request.query_params.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(sku__icontains=search_query)
                | Q(brand__name__icontains=search_query)
            )

        # Apply category filter
        category_id = request.query_params.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Apply brand filter
        brand_id = request.query_params.get("brand")
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)

        # Apply price range filter
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        if min_price:
            queryset = queryset.filter(regular_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(regular_price__lte=max_price)

        # Handle pagination
        no_page = request.query_params.get("no_page", "false").lower() == "true"
        if no_page:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=["GET"])
    def search(self, request):
        """
        Search products across multiple fields with optional filters
        """
        query = request.query_params.get("q")
        if not query or len(query) < 2:
            return Response(
                {"error": "Search query must be at least 2 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize the queryset
        queryset = self.get_queryset()

        # Build search filters - search across multiple fields
        search_fields = (
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(sku__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(category__name__icontains=query)
        )

        # Apply the search
        products = queryset.filter(search_fields)

        # Apply additional filters if provided
        category_slug = request.query_params.get("category")
        if category_slug:
            from categories.models import Category

            try:
                category = Category.objects.get(slug=category_slug)
                # Check if we should include subcategories
                include_subcategories = (
                    request.query_params.get("include_subcategories", "true").lower()
                    == "true"
                )
                if include_subcategories:
                    descendant_categories = list(
                        category.get_descendants(include_self=True)
                    )
                    products = products.filter(category__in=descendant_categories)
                else:
                    products = products.filter(category=category)
            except Category.DoesNotExist:
                pass

        # Filter by brand if provided
        brand_slug = request.query_params.get("brand")
        if brand_slug:
            products = products.filter(brand__slug=brand_slug)

        # Filter by active status
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            is_active = is_active.lower() == "true"
            products = products.filter(is_active=is_active)
        else:
            # Default to active products only
            products = products.filter(is_active=True)

        # Filter by product status
        product_status = request.query_params.get("status")
        if product_status:
            products = products.filter(status=product_status)
        else:
            # Default to published products
            products = products.filter(status="published")

        # Price range filtering
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")

        if min_price:
            products = products.filter(sale_price__gte=float(min_price))
        if max_price:
            products = products.filter(sale_price__lte=float(max_price))

        # Sort results
        sort_by = request.query_params.get("sort_by", "relevance")
        if sort_by == "relevance":
            # For relevance sorting, we can use annotate to add a custom field
            # that gives higher score to products where the query matches the name
            from django.db.models.functions import Length

            products = products.annotate(
                name_match_score=Length("name")
                - Length(Replace("name", Value(query), Value("")))
            ).order_by("-name_match_score", "-is_featured")
        else:
            # Handle other sorting options
            sort_dir = request.query_params.get("sort_dir", "desc")
            if sort_dir == "desc":
                sort_by = f"-{sort_by}"
            products = products.order_by(sort_by)

        # Remove duplicates (if any)
        products = products.distinct()

        # Apply pagination
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(products, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=["GET"])
    def color_images(self, request, slug=None):
        """
        Get images for a specific color
        """
        product = get_object_or_404(Product, slug=slug)
        print("inside color images")
        color = request.query_params.get("color")

        if not color:
            return Response(
                {"error": "Color parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all images for this color
        images = product.images.filter(color_attribute=color)

        # If no color-specific images, return default product images
        if not images.exists():
            images = product.images.filter(color_attribute__isnull=True)

        serializer = ProductImageSerializer(images, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def upload_color_images(self, request, slug=None):
        """Upload images for specific color variants"""
        product = get_object_or_404(Product, slug=slug)

        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        color = request.data.get("color")
        if not color:
            return Response(
                {"error": "Color attribute is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        color_attr, created = ProductAttribute.objects.get_or_create(
            product=product,
            attribute_type="color",
            value=color,
            defaults={
                "name": "Color",
                "is_visible": True,
                "is_variation": True,
                "is_searchable": True,
                "sort_order": 0,
            },
        )

        if created:
            # Validate the color value against constants
            try:
                color_attr.clean()  # This will set the display_value
                color_attr.save()
            except ValidationError as e:
                # Delete the created attribute if validation fails
                color_attr.delete()
                return Response(
                    {
                        "error": f"Invalid color '{color}'. Must be one of the predefined colors."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        images = request.FILES.getlist("images")
        if not images:
            return Response(
                {"error": "No images provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        image_service = ImageService()
        uploaded_images = []

        for image in images:
            file_path, file_url = image_service.upload_image(
                image, str(product.id), product.name
            )
            # Create image record with color attribute
            image_data = {
                "product": product.id,
                "image_url": file_url,
                "storage_path": file_path,
                "alt_text": request.data.get("alt_text", f"{product.name} - {color}"),
                "color_attribute": color,
                "is_primary": request.data.get("is_primary", False),
            }
            image_serializer = ProductImageSerializer(data=image_data)
            if image_serializer.is_valid():
                image_obj = image_serializer.save()
                uploaded_images.append(image_serializer.data)
            else:
                return Response(
                    image_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

        response_data = {
            "uploaded_images": uploaded_images,
            "color_attribute_created": created,
            "message": f"Successfully uploaded {len(uploaded_images)} images for color '{color}'",
        }

        if created:
            response_data["message"] += f" and created color attribute"

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["GET"])
    def available_options(self, request, slug=None):
        """Get available color and size options for a product"""
        product = self.get_object()

        # Get options from variants
        variants = ProductVariant.objects.filter(
            product=product, is_active=True
        ).prefetch_related("variant_attributes")

        colors = {}
        sizes = {}

        for variant in variants:
            for attr in variant.variant_attributes.all():
                if attr.attribute_type == "color":
                    colors[attr.value] = attr.display_value
                elif attr.attribute_type == "size":
                    sizes[attr.value] = attr.display_value

        return Response(
            {
                "colors": [{"value": k, "display": v} for k, v in colors.items()],
                "sizes": [{"value": k, "display": v} for k, v in sizes.items()],
            }
        )

    @action(detail=True, methods=["GET"])
    def check_variant_availability(self, request, slug=None):
        """Check availability of specific variant combination"""
        product = self.get_object()

        color = request.query_params.get("color")
        size = request.query_params.get("size")

        if not color or not size:
            return Response(
                {"error": "Both color and size are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find matching variant
        variant = (
            ProductVariant.objects.filter(
                product=product,
                is_active=True,
                variant_attributes__attribute_type="color",
                variant_attributes__value=color,
            )
            .filter(
                variant_attributes__attribute_type="size",
                variant_attributes__value=size,
            )
            .first()
        )

        if variant:
            return Response(
                {
                    "available": True,
                    "variant_id": variant.id,
                    "sku": variant.sku,
                    "stock": variant.stock_quantity,
                    "price": variant.get_price(),
                    "in_stock": variant.stock_quantity > 0,
                }
            )
        else:
            return Response(
                {"available": False, "message": "This combination is not available"}
            )

    # ========== MISSING METHODS FROM ORIGINAL FILE ==========

    @action(detail=True, methods=["GET"])
    def mobile_variant_selector(self, request, slug=None):
        """
        Mobile-optimized variant selector - using variant attributes instead of product attributes
        """
        product = get_object_or_404(Product, slug=slug)

        # Get all unique colors from variant attributes instead of product attributes
        color_values = (
            VariantAttribute.objects.filter(
                variant__product=product,
                attribute_type="color",
                variant__is_active=True,
            )
            .values_list("value", "display_value")
            .distinct()
        )

        colors = []
        for color_value, color_display in color_values:
            # Get primary image for this color
            color_image = product.images.filter(
                color_attribute=color_value, is_primary=True
            ).first()

            image_url = color_image.image_url if color_image else None

            # Get available sizes for this color
            available_sizes = []
            for variant in product.variants.filter(
                variant_attributes__attribute_type="color",
                variant_attributes__value=color_value,
                is_active=True,
            ):
                # Get size attribute for this variant
                size_attr = variant.variant_attributes.filter(
                    attribute_type="size"
                ).first()
                if size_attr:  # Note: Include even if stock is 0, but mark it
                    available_sizes.append(
                        {
                            "size_value": size_attr.value,
                            "size_display": size_attr.display_value,
                            "variant_id": variant.id,
                            "price": variant.get_price(),
                            "stock": variant.stock_quantity,
                            "in_stock": variant.stock_quantity > 0,
                        }
                    )

            colors.append(
                {
                    "color_value": color_value,
                    "color_display": color_display,
                    "image_url": image_url,
                    "available_sizes": available_sizes,
                    "has_stock": any(size["stock"] > 0 for size in available_sizes),
                }
            )

        return Response(
            {
                "product_id": product.id,
                "product_name": product.name,
                "base_price": product.sale_price,
                "colors": colors,
            }
        )

    @action(detail=True, methods=["GET"])
    def variant_detail(self, request, slug=None, variant_slug=None):
        """
        Get variant details with SEO-friendly URL
        """
        product = get_object_or_404(Product, slug=slug)
        variant = get_object_or_404(
            ProductVariant, product=product, variant_slug=variant_slug
        )

        # Combine product and variant data
        product_data = ProductDetailSerializer(product).data
        variant_data = ProductVariantDetailSerializer(variant).data

        # Override product data with variant-specific data
        result = {**product_data}
        result["selected_variant"] = variant_data
        result["price"] = variant.get_price()
        result["stock_quantity"] = variant.stock_quantity

        # Get variant-specific images
        color_attr = variant.variant_attributes.filter(attribute_type="color").first()
        if color_attr:
            color_images = product.images.filter(color_attribute=color_attr.value)
            if color_images.exists():
                result["images"] = ProductImageSerializer(color_images, many=True).data

        return Response(result)

    @action(detail=False, methods=["POST"])
    def bulk_update_variant_stock(self, request):
        """
        Bulk update stock for multiple variants
        """
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        updates = request.data.get("updates", [])
        if not updates:
            return Response(
                {"error": "No updates provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        results = []
        errors = []

        for update in updates:
            variant_id = update.get("variant_id")
            new_quantity = update.get("quantity")

            if not variant_id or new_quantity is None:
                errors.append(
                    {"error": "Missing variant_id or quantity", "update": update}
                )
                continue

            try:
                variant = ProductVariant.objects.get(id=variant_id)

                # Check if user has permission to update this variant
                if not (
                    request.user.is_staff or request.user == variant.product.seller
                ):
                    errors.append(
                        {
                            "error": "No permission for this variant",
                            "variant_id": variant_id,
                        }
                    )
                    continue

                # Update stock quantity
                variant.stock_quantity = new_quantity
                variant.save()

                results.append(
                    {
                        "variant_id": variant_id,
                        "sku": variant.sku,
                        "new_quantity": variant.stock_quantity,
                    }
                )

            except ProductVariant.DoesNotExist:
                errors.append({"error": "Variant not found", "variant_id": variant_id})

        return Response(
            {
                "success": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors,
            }
        )

    @action(detail=True, methods=["POST"])
    def track_product_view(self, request, slug=None):
        """
        Track product view with variant selection for recently viewed products
        """
        product = get_object_or_404(Product, slug=slug)
        variant_id = request.data.get("variant_id")

        # Update product view count
        product.view_count = F("view_count") + 1
        product.save(update_fields=["view_count"])

        # For authenticated users, store in database
        if request.user.is_authenticated:
            variant = None
            if variant_id:
                try:
                    variant = ProductVariant.objects.get(id=variant_id, product=product)
                    # Update variant view count
                    variant.view_count = F("view_count") + 1
                    variant.last_viewed_at = now()
                    variant.save(update_fields=["view_count", "last_viewed_at"])
                except ProductVariant.DoesNotExist:
                    pass

            # Create or update recently viewed record
            try:
                from .models import RecentlyViewedProduct

                RecentlyViewedProduct.objects.update_or_create(
                    user=request.user,
                    product=product,
                    defaults={"variant": variant, "viewed_at": now()},
                )
            except ImportError:
                pass  # Model doesn't exist

            # Create activity record if CustomerActivity model exists
            try:
                from customers.models import CustomerActivity

                CustomerActivity.objects.create(
                    customer=request.user.customer,
                    product_id=product.id,
                    interaction_type="view",
                    category_id=product.category_id,
                )
            except (ImportError, AttributeError):
                pass  # Model doesn't exist or user doesn't have customer

        # For anonymous users, store in session
        else:
            if "recently_viewed" not in request.session:
                request.session["recently_viewed"] = []

            # Add to recently viewed, avoid duplicates
            recently_viewed = request.session["recently_viewed"]

            # Remove if already exists
            recently_viewed = [
                item
                for item in recently_viewed
                if item.get("product_id") != str(product.id)
            ]

            # Add to front of list
            recently_viewed.insert(
                0,
                {
                    "product_id": str(product.id),
                    "variant_id": variant_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Limit list size
            request.session["recently_viewed"] = recently_viewed[:10]
            request.session.modified = True

        return Response({"status": "success"})

    @action(detail=False, methods=["GET"])
    def recently_viewed(self, request):
        """
        Get recently viewed products
        """
        if request.user.is_authenticated:
            try:
                from .models import RecentlyViewedProduct
                from .serializers import RecentlyViewedProductSerializer

                # Get from database for authenticated users
                recent_views = RecentlyViewedProduct.objects.filter(
                    user=request.user
                ).select_related("product", "variant")[:10]

                serializer = RecentlyViewedProductSerializer(recent_views, many=True)
                return Response(serializer.data)
            except ImportError:
                # Model doesn't exist, return empty list
                return Response([])
        else:
            # Get from session for anonymous users
            if "recently_viewed" not in request.session:
                return Response([])

            recent_views = request.session["recently_viewed"]

            # Fetch product details
            products = []
            for item in recent_views:
                try:
                    product = Product.objects.get(id=item.get("product_id"))

                    variant_details = None
                    if item.get("variant_id"):
                        try:
                            variant = ProductVariant.objects.get(
                                id=item.get("variant_id")
                            )
                            variant_details = ProductVariantSerializer(variant).data
                        except ProductVariant.DoesNotExist:
                            pass

                    from .serializers import ProductMinimalSerializer

                    products.append(
                        {
                            "product": ProductMinimalSerializer(product).data,
                            "variant_details": variant_details,
                            "viewed_at": item.get("timestamp"),
                        }
                    )
                except Product.DoesNotExist:
                    continue

            return Response(products)

    @action(detail=False, methods=["GET"])
    def complementary_products(self, request):
        """
        Get complementary products for a product or based on cart
        """
        product_id = request.query_params.get("product_id")

        if product_id:
            # Get complementary products for specific product
            try:
                product = Product.objects.get(id=product_id)

                # Find products in the same category
                same_category = (
                    Product.objects.filter(
                        category=product.category, is_active=True, status="published"
                    )
                    .exclude(id=product.id)
                    .order_by("-is_featured")[:4]
                )

                # Find products with the same brand
                same_brand = (
                    Product.objects.filter(
                        brand=product.brand, is_active=True, status="published"
                    )
                    .exclude(id=product.id)
                    .order_by("-is_featured")[:4]
                )

                # Find frequently bought together
                # This would ideally be based on order data
                # For now, just select some popular products
                popular_products = (
                    Product.objects.filter(is_active=True, status="published")
                    .exclude(id=product.id)
                    .order_by("-view_count")[:4]
                )

                return Response(
                    {
                        "complementary_categories": [
                            {
                                "title": "Similar Products",
                                "products": ProductListSerializer(
                                    same_category, many=True
                                ).data,
                            },
                            {
                                "title": f"More from {product.brand.name}",
                                "products": ProductListSerializer(
                                    same_brand, many=True
                                ).data,
                            },
                            {
                                "title": "Frequently Bought Together",
                                "products": ProductListSerializer(
                                    popular_products, many=True
                                ).data,
                            },
                        ]
                    }
                )

            except Product.DoesNotExist:
                return Response(
                    {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get recommendations based on cart items
            if request.user.is_authenticated and hasattr(request.user, "customer"):
                try:
                    cart_items = request.user.customer.cart_items.all()

                    if not cart_items.exists():
                        return Response({"complementary_categories": []})

                    # Get categories of products in cart
                    category_ids = set()
                    for item in cart_items:
                        try:
                            product = Product.objects.get(id=item.product_id)
                            category_ids.add(product.category_id)
                        except Product.DoesNotExist:
                            continue

                    # Get products from those categories
                    products = (
                        Product.objects.filter(
                            category_id__in=category_ids,
                            is_active=True,
                            status="published",
                        )
                        .exclude(id__in=[item.product_id for item in cart_items])
                        .order_by("-is_featured")[:8]
                    )

                    return Response(
                        {
                            "complementary_categories": [
                                {
                                    "title": "Complete Your Purchase",
                                    "products": ProductListSerializer(
                                        products, many=True
                                    ).data,
                                }
                            ]
                        }
                    )
                except AttributeError:
                    # User doesn't have customer attribute
                    pass

            return Response({"complementary_categories": []})


class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for ProductReview model."""

    product = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "product",
            "user",
            "rating",
            "title",
            "comment",
            "is_verified",
            "is_approved",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "is_approved",
            "created_at",
            "updated_at",
        ]

    def validate_rating(self, value):
        """Validate rating value."""
        if value < 1 or value > 5:
            raise ValidationError("Rating must be between 1 and 5.")
        return value


class ProductStockSerializer(serializers.ModelSerializer):
    """Serializer for ProductStock model."""

    product = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProductStock
        fields = [
            "id",
            "product",
            "warehouse",
            "quantity",
            "batch_number",
            "expiry_date",
        ]
        read_only_fields = ["id"]

    def validate_quantity(self, value):
        """Validate quantity value."""
        if value < 0:
            raise ValidationError("Quantity cannot be negative.")
        return value


class ProductMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for Product model."""

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "regular_price", "sale_price"]


class ProductListSerializer(serializers.ModelSerializer):
    """List serializer for Product model."""

    brand = BrandSerializer(read_only=True)
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    seller_info = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "brand",
            "regular_price",
            "sale_price",
            "stock_quantity",
            "is_active",
            "is_featured",
            "images",
            "created_at",
            "seller_info",
        ]
        read_only_fields = ["id", "slug", "created_at", "seller_info"]

    def get_seller_info(self, obj):
        """Get seller details associated with the product"""
        if hasattr(obj.seller, "seller_profile") and obj.seller.seller_profile:
            return SellerInfoSerializer(obj.seller.seller_profile).data
        # Return basic seller information if seller profile doesn't exist
        return {
            "id": None,
            "user_name": obj.seller.name,
            "email": obj.seller.email,
            "business_name": "Not available",
            "is_email_verified": False,
        }


class ProductSerializer(serializers.ModelSerializer):
    """Base serializer for Product model"""

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "brand",
            "regular_price",
            "sale_price",
            "stock_quantity",
            "status",
            "is_active",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Product model."""

    brand = BrandSerializer(read_only=True)
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    videos = ProductVideoSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    stock_entries = ProductStockSerializer(many=True, read_only=True)
    seller_info = serializers.SerializerMethodField()
    variants = ProductVariantSerializer(many=True, read_only=True)

    # New field for color variant images
    color_images = serializers.SerializerMethodField()
    # Available colors and sizes
    available_colors = serializers.SerializerMethodField()
    available_sizes = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "short_description",
            "category",
            "brand",
            "regular_price",
            "sale_price",
            "cost_price",
            "stock_quantity",
            "is_active",
            "is_featured",
            # Tax fields
            "hsn_code",
            "sac_code",
            "gst_rate",
            "tax_included",
            # Dimension fields
            "weight",
            "length",
            "width",
            "height",
            # Inventory fields
            "allow_backorder",
            "is_digital",
            "low_stock_threshold",
            # Status field
            "status",
            # Relationship fields
            "images",
            "videos",
            "attributes",
            "reviews",
            "stock_entries",
            "created_at",
            "updated_at",
            "shipping_policy_id",
            "shipping_policy_data",
            "seller_info",
            "variants",
            "color_images",
            "available_colors",
            "available_sizes",
            # SEO fields
            "meta_title",
            "meta_description",
            "meta_keywords",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "updated_at",
            "shipping_policy_data",
            "seller_info",
            "variants",
            "color_images",
            "available_colors",
            "available_sizes",
        ]

    def get_seller_info(self, obj):
        """Get seller details associated with the product"""
        if hasattr(obj.seller, "seller_profile") and obj.seller.seller_profile:
            return SellerInfoSerializer(obj.seller.seller_profile).data
        # Return basic seller information if seller profile doesn't exist
        return {
            "id": None,
            "user_name": obj.seller.name,
            "email": obj.seller.email,
            "business_name": "Not available",
            "is_email_verified": False,
        }

    def get_color_images(self, obj):
        """Group images by color"""
        result = {}

        # Get product images with color attributes
        for image in obj.images.all():
            if image.color_attribute:
                if image.color_attribute not in result:
                    result[image.color_attribute] = []

                result[image.color_attribute].append(ProductImageSerializer(image).data)

        return result

    def get_available_colors(self, obj):
        """Get unique colors from variants"""
        # Collect unique colors from variant attributes
        colors = set()
        color_data = []

        # First check product attribute-based colors
        for attr in obj.attributes.filter(attribute_type="color"):
            colors.add(attr.value)
            color_data.append(
                {
                    "value": attr.value,
                    "display_value": attr.display_value,
                    "has_image": obj.images.filter(color_attribute=attr.value).exists(),
                }
            )

        # Check variant-based colors too
        for variant in obj.variants.all():
            for attr in variant.variant_attributes.filter(attribute_type="color"):
                if attr.value not in colors:
                    colors.add(attr.value)
                    color_data.append(
                        {
                            "value": attr.value,
                            "display_value": attr.display_value,
                            "has_image": obj.images.filter(
                                color_attribute=attr.value
                            ).exists(),
                        }
                    )

        return color_data

    def get_available_sizes(self, obj):
        """Get unique sizes from variants, grouped by color"""
        # Structure: { "color_value": [{"size": "M", "stock": 5}, ...] }
        result = {}

        # Process all variants to gather size data
        for variant in obj.variants.filter(is_active=True):
            # Get color and size attributes for this variant
            color_attr = variant.variant_attributes.filter(
                attribute_type="color"
            ).first()
            size_attr = variant.variant_attributes.filter(attribute_type="size").first()

            if color_attr and size_attr:
                color_value = color_attr.value

                if color_value not in result:
                    result[color_value] = []

                result[color_value].append(
                    {
                        "size_value": size_attr.value,
                        "size_display": size_attr.display_value,
                        "stock": variant.stock_quantity,
                        "variant_id": variant.id,
                        "price": variant.get_price(),
                    }
                )

        return result


class WishlistItemSerializer(serializers.Serializer):
    """
    Detailed Wishlist Item Serializer
    """

    class Meta:
        fields = ["id", "product", "added_at"]

    product = ProductDetailSerializer(read_only=True)
    added_at = serializers.DateTimeField(read_only=True)


class WishlistSerializer(serializers.Serializer):
    """
    Serializer for Wishlist Management
    """

    class Meta:
        fields = ["id", "user", "product", "added_at"]

    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    product = ProductMinimalSerializer(read_only=True)
    added_at = serializers.DateTimeField(read_only=True)

    def validate(self, data):
        """
        Validate wishlist entry
        - Check if product already exists in user's wishlist
        - Validate product availability
        """
        user = self.context.get("request").user
        product = data.get("product")

        # Check if product is already in wishlist
        if WishlistItem.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError("Product already in wishlist")

        return data


class CartItemSerializer(serializers.Serializer):
    """Serializer for Cart Items"""

    product = ProductMinimalSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=100,
        error_messages={
            "min_value": "Quantity must be at least 1.",
            "max_value": "Maximum quantity is 100.",
        },
    )
    variant_id = serializers.CharField(max_length=255, required=False, allow_null=True)
    added_at = serializers.DateTimeField(read_only=True)

    def validate_quantity(self, value):
        """Validate cart item quantity against product stock."""
        product = self.context.get("product")
        if product and value > product.stock_quantity:
            raise ValidationError(
                f"Not enough stock. Available: {product.stock_quantity}"
            )
        return value

    class Meta:
        fields = ["product", "user", "quantity", "variant_id", "added_at"]


class ProductAvailabilitySerializer(serializers.Serializer):
    """
    Serializer for Product Availability Checks
    """

    class Meta:
        fields = [
            "product",
            "is_available",
            "available_quantity",
            "can_backorder",
            "estimated_restock_date",
        ]

    product = ProductMinimalSerializer(read_only=True)
    is_available = serializers.BooleanField()
    available_quantity = serializers.IntegerField()
    can_backorder = serializers.BooleanField()
    estimated_restock_date = serializers.DateField(allow_null=True)


class ProductStockAlertSerializer(serializers.Serializer):
    """
    Serializer for Product Stock Alerts
    """

    class Meta:
        fields = ["product", "current_stock", "low_stock_threshold", "is_low_stock"]

    product = ProductMinimalSerializer(read_only=True)
    current_stock = serializers.IntegerField()
    low_stock_threshold = serializers.IntegerField()
    is_low_stock = serializers.BooleanField()


class ProductFeatureRequestSerializer(serializers.ModelSerializer):
    """Serializer for product feature requests"""

    product_details = ProductMinimalSerializer(source="product", read_only=True)
    requested_by_details = serializers.SerializerMethodField()
    reviewed_by_details = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ProductFeatureRequest
        fields = [
            "id",
            "product",
            "product_details",
            "reason",
            "contact_name",
            "contact_email",
            "contact_phone",
            "status",
            "status_display",
            "admin_notes",
            "requested_by",
            "requested_by_details",
            "reviewed_by",
            "reviewed_by_details",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requested_by",
            "status",
            "admin_notes",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def get_requested_by_details(self, obj):
        if obj.requested_by:
            return {
                "id": str(obj.requested_by.id),
                "email": obj.requested_by.email,
                "name": (
                    obj.requested_by.name
                    if hasattr(obj.requested_by, "name")
                    else obj.requested_by.email
                ),
            }
        return None

    def get_reviewed_by_details(self, obj):
        if obj.reviewed_by:
            return {
                "id": str(obj.reviewed_by.id),
                "email": obj.reviewed_by.email,
                "name": (
                    obj.reviewed_by.name
                    if hasattr(obj.reviewed_by, "name")
                    else obj.reviewed_by.email
                ),
            }
        return None

    def validate(self, data):
        """
        Validate product feature request
        - Make sure product belongs to the current user
        - Check if there's already a pending request for this product
        """
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")

        product = data.get("product")
        if not product:
            raise serializers.ValidationError("Product is required")

        # Ensure product belongs to the current user
        if product.seller != request.user:
            raise serializers.ValidationError(
                "You can only request to feature your own products"
            )

        # Check for existing pending requests
        existing_request = ProductFeatureRequest.objects.filter(
            product=product, status="pending"
        ).exists()

        if existing_request:
            raise serializers.ValidationError(
                "There is already a pending feature request for this product"
            )

        return data


class ProductReviewViewSet(viewsets.ModelViewSet):
    """
    Multi-Vendor Product Review Management
    """

    serializer_class = ProductReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """
        Customize review queryset for multi-vendor context
        """
        queryset = ProductReview.objects.select_related("product", "user")
        user = self.request.user

        # Filter by product if specified in query params
        product_id = self.request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # For anonymous users, only show approved reviews
        if not user.is_authenticated:
            queryset = queryset.filter(is_approved=True)

        # For authenticated users
        elif user.is_authenticated:
            # For staff users, show all reviews
            if user.is_staff:
                # No additional filtering for staff
                pass
            else:
                # For sellers: only show reviews for THEIR products + their own reviews on other products
                # This is the key fix - filter by products that belong to this seller
                seller_product_reviews = Q(product__seller=user)
                own_reviews = Q(user=user)

                queryset = queryset.filter(
                    seller_product_reviews | own_reviews
                ).distinct()

        return queryset.order_by("-created_at")

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ["list", "retrieve"]:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """
        Validate and create review with user context
        """
        product_slug = self.request.data.get("product_slug")
        if not product_slug:
            raise ValidationError("product_slug is required")

        try:
            product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            raise ValidationError("Product not found")

        # Check if user has already reviewed this product
        if ProductReview.objects.filter(
            product=product, user=self.request.user
        ).exists():
            raise ValidationError("You have already reviewed this product")

        # Save the review
        serializer.save(product=product, user=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Override list to add rating statistics
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Calculate statistics for the filtered queryset
        total_reviews = queryset.count()
        avg_rating = queryset.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0

        # Rating distribution
        rating_distribution = {
            5: queryset.filter(rating=5).count(),
            4: queryset.filter(rating=4).count(),
            3: queryset.filter(rating=3).count(),
            2: queryset.filter(rating=2).count(),
            1: queryset.filter(rating=1).count(),
        }

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            # Add statistics to paginated response
            response.data["statistics"] = {
                "total_reviews": total_reviews,
                "average_rating": round(avg_rating, 1),
                "rating_distribution": rating_distribution,
            }
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "results": serializer.data,
                "statistics": {
                    "total_reviews": total_reviews,
                    "average_rating": round(avg_rating, 1),
                    "rating_distribution": rating_distribution,
                },
            }
        )

    @action(
        detail=True,
        methods=["POST"],
        permission_classes=[IsAuthenticated],
    )
    def mark_helpful(self, request, pk=None):
        """
        Mark a review as helpful (placeholder for future implementation)
        """
        review = get_object_or_404(ProductReview, id=pk)

        # This is a placeholder - you'd need to implement a helpful tracking system
        # For now, just return success
        return Response(
            {"message": "Review marked as helpful", "review_id": review.id},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["POST"],
        permission_classes=[IsAuthenticated, HasModulePermission],
    )
    def approve(self, request, pk=None):
        """
        Approve a review (for seller or staff)
        """
        review = get_object_or_404(ProductReview, id=pk)

        # Only product seller or staff can approve reviews
        if not request.user.is_staff and review.product.seller != request.user:
            return Response(
                {"error": "You can only approve reviews for your own products."},
                status=status.HTTP_403_FORBIDDEN,
            )

        review.is_approved = True
        review.save()

        return Response(
            {"message": "Review approved successfully"}, status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=["POST"],
        permission_classes=[IsAuthenticated, HasModulePermission],
    )
    def reject(self, request, pk=None):
        """
        Reject a review (for seller or staff)
        """
        review = get_object_or_404(ProductReview, id=pk)

        # Only product seller or staff can reject reviews
        if not request.user.is_staff and review.product.seller != request.user:
            return Response(
                {"error": "You can only reject reviews for your own products."},
                status=status.HTTP_403_FORBIDDEN,
            )

        review.is_approved = False
        review.save()

        return Response(
            {"message": "Review rejected successfully"}, status=status.HTTP_200_OK
        )


class ProductStockViewSet(viewsets.ModelViewSet):
    """
    Multi-Vendor Product Stock Management
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Limit stock entries to seller's products
        """
        if self.request.user.is_staff:
            return ProductStock.objects.all()

        return ProductStock.objects.filter(product__seller=self.request.user)

    @action(detail=False, methods=["POST"])
    def update_stock(self, request):
        """
        Bulk stock update for vendor
        """
        stock_updates = request.data.get("stock_updates", [])

        if not stock_updates:
            return Response(
                {"error": "No stock updates provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_stocks = []

        for update in stock_updates:
            try:
                product = Product.objects.get(
                    slug=update.get("product_slug"), created_by=request.user
                )

                quantity_change = update.get("quantity_change", 0)
                product.update_stock(quantity_change)

                updated_stocks.append(
                    {"product_slug": product.slug, "new_stock": product.stock_quantity}
                )

            except Product.DoesNotExist:
                return Response(
                    {"error": f"Product not found: {update.get('product_slug')}"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"message": "Stock updated successfully", "updated_stocks": updated_stocks},
            status=status.HTTP_200_OK,
        )


class BulkUpdateProductsView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]

    def post(self, request, *args, **kwargs):
        # Check if a CSV file is provided
        if "file" not in request.FILES:
            return Response(
                {"error": "No CSV file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        file = request.FILES["file"]
        decoded_file = TextIOWrapper(file, encoding="utf-8")
        reader = csv.DictReader(decoded_file)

        updated_products = []
        errors = []

        for row in reader:
            try:
                # Fetch the product by SKU or ID
                product = Product.objects.get(
                    sku=row["sku"]
                )  # Assuming 'sku' is a unique identifier
                # Update product fields
                for field, value in row.items():
                    if field != "sku" and hasattr(product, field):
                        setattr(product, field, value)
                product.save()
                updated_products.append(product)
            except Product.DoesNotExist:
                errors.append(f"Product with SKU {row['sku']} does not exist.")
            except Exception as e:
                errors.append(f"Error updating product with SKU {row['sku']}: {str(e)}")

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ProductSerializer(updated_products, many=True)
        return Response(
            {"message": "Products updated successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )


class BulkDownloadProductsView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]

    def get(self, request, *args, **kwargs):
        # Get query parameters for filtering
        category_id = request.query_params.get("category_id")
        brand_id = request.query_params.get("brand_id")

        # Filter products based on query parameters
        products = Product.objects.all()
        if category_id:
            products = products.filter(category_id=category_id)
        if brand_id:
            products = products.filter(brand_id=brand_id)

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="products.csv"'

        writer = csv.writer(response)
        # Write CSV header
        writer.writerow(
            [
                "SKU",
                "Name",
                "Description",
                "Category",
                "Brand",
                "Regular Price",
                "Sale Price",
                "Stock Quantity",
            ]
        )

        # Write product data
        for product in products:
            writer.writerow(
                [
                    product.sku,
                    product.name,
                    product.description,
                    product.category.name if product.category else "",
                    product.brand.name if product.brand else "",
                    product.regular_price,
                    product.sale_price,
                    product.stock_quantity,
                ]
            )

        return response


class BulkCreateProductsView(APIView):
    permission_classes = [IsAuthenticated, HasModulePermission]

    def validate_row(self, row, line_number):
        """Validate a single row of data"""
        errors = []

        # Check required fields
        required_fields = [
            "sku",
            "name",
            "brand",
            "category",
            "regular_price",
            "sale_price",
            "stock_quantity",
        ]
        for field in required_fields:
            if not row.get(field):
                errors.append(f"Line {line_number}: Missing required field '{field}'")

        # Validate SKU uniqueness
        if row.get("sku") and Product.objects.filter(sku=row["sku"]).exists():
            errors.append(f"Line {line_number}: SKU '{row['sku']}' already exists")

        # Validate prices
        try:
            if row.get("regular_price"):
                Decimal(row["regular_price"])
            if row.get("sale_price"):
                Decimal(row["sale_price"])
        except:
            errors.append(f"Line {line_number}: Invalid price format")

        # Validate stock quantity
        try:
            if row.get("stock_quantity"):
                int(row["stock_quantity"])
        except:
            errors.append(f"Line {line_number}: Invalid stock quantity")

        # Validate brand
        try:
            brand_id = int(row.get("brand", 0))
            if not Brand.objects.filter(id=brand_id).exists():
                errors.append(
                    f"Line {line_number}: Brand with ID {brand_id} does not exist"
                )
        except ValueError:
            errors.append(f"Line {line_number}: Invalid brand ID format")

        # Validate category
        try:
            if not Category.objects.filter(id=row.get("category")).exists():
                errors.append(f"Line {line_number}: Category ID does not exist")
        except:
            errors.append(f"Line {line_number}: Invalid category ID format")

        return errors

    def post(self, request, *args, **kwargs):
        if "file" not in request.FILES:
            return Response(
                {"error": "No CSV file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        file = request.FILES["file"]
        if not file.name.endswith(".csv"):
            return Response(
                {"error": "File must be a CSV."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Process CSV file
        decoded_file = TextIOWrapper(file, encoding="utf-8")
        reader = csv.DictReader(decoded_file)

        # Validate all rows first
        all_errors = []
        valid_rows = []

        for line_number, row in enumerate(
            reader, start=2
        ):  # Start at 2 to account for header row
            errors = self.validate_row(row, line_number)
            if errors:
                all_errors.extend(errors)
            else:
                valid_rows.append(row)

        if all_errors:
            return Response({"errors": all_errors}, status=status.HTTP_400_BAD_REQUEST)

        # Create products if all rows are valid
        created_products = []
        try:
            for row in valid_rows:
                # Get brand and category instances
                brand = Brand.objects.get(id=int(row["brand"]))
                category = Category.objects.get(id=row["category"])

                product = Product.objects.create(
                    sku=row["sku"],
                    name=row["name"],
                    description=row.get("description", ""),
                    regular_price=Decimal(row["regular_price"]),
                    sale_price=Decimal(row["sale_price"]),
                    stock_quantity=int(row["stock_quantity"]),
                    brand=brand,  # Use the brand instance
                    category=category,  # Use the category instance
                    seller=request.user,
                    created_by=request.user,
                    updated_by=request.user,
                    is_active=row.get("is_active", "true").lower() == "true",
                    status=row.get("status", "draft"),
                )
                created_products.append(product)

        except Exception as e:
            # Rollback by deleting any products created in this batch
            for product in created_products:
                product.delete()
            return Response(
                {"error": f"Error creating products: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Products created successfully.",
                "created_count": len(created_products),
            },
            status=status.HTTP_201_CREATED,
        )


# products/views.py - Update the BrandViewSet


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def perform_create(self, serializer):
        # Set created_by and updated_by to the current user
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        # Set updated_by to the current user
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """
        Override perform_destroy to add permission checks and cleanup
        """
        # Check permissions - only staff or brand creator can delete
        if not (self.request.user.is_staff or self.request.user == instance.created_by):
            raise PermissionDenied("You don't have permission to delete this brand")

        # Check if brand has any products associated
        if instance.products.exists():
            raise ValidationError(
                "Cannot delete brand with associated products. Please remove or reassign products first."
            )

        # Clean up logo from storage if exists
        if instance.logo_storage_path:
            try:
                image_service = ImageService()
                image_service.delete_image(instance.logo_storage_path)
            except Exception as e:
                logger.warning(f"Failed to delete brand logo from storage: {str(e)}")

        # Delete the brand
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        """
        Override destroy to provide better error handling and responses
        """
        try:
            instance = self.get_object()
            brand_name = instance.name

            # Perform the deletion
            self.perform_destroy(instance)

            return Response(
                {
                    "message": f"Brand '{brand_name}' deleted successfully",
                    "status": "success",
                },
                status=status.HTTP_200_OK,
            )

        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Brand.DoesNotExist:
            return Response(
                {"error": "Brand not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting brand: {str(e)}")
            return Response(
                {"error": f"Failed to delete brand: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    def upload_logo(self, request, slug=None):
        """Upload logo for brand"""
        brand = self.get_object()

        # Check permissions - only staff or brand creator can upload
        if not (request.user.is_staff or request.user == brand.created_by):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        logo_file = request.FILES.get("logo")
        if not logo_file:
            return Response(
                {"error": "No logo file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Use the existing ImageService for uploading
            image_service = ImageService()

            # Create a unique filename for the brand logo
            custom_name = f"brand_{brand.slug}_logo"

            # Upload the logo
            file_path, file_url = image_service.upload_image(
                logo_file, f"brands/{brand.id}", custom_name
            )

            # Update the brand with the new logo URL and path
            brand.logo = file_url
            brand.logo_storage_path = file_path
            brand.updated_by = request.user
            brand.save()

            # Return updated brand data
            serializer = self.get_serializer(brand)
            return Response(
                {
                    "message": "Brand logo uploaded successfully",
                    "brand": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error uploading brand logo: {str(e)}")
            return Response(
                {"error": f"Failed to upload logo: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["DELETE"])
    def delete_logo(self, request, slug=None):
        """Delete brand logo"""
        brand = self.get_object()

        # Check permissions
        if not (request.user.is_staff or request.user == brand.created_by):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        if not brand.logo_storage_path:
            return Response({"message": "No logo to delete"}, status=status.HTTP_200_OK)

        try:
            # Delete from Firebase Storage
            image_service = ImageService()
            if image_service.delete_image(brand.logo_storage_path):
                # Clear logo fields
                brand.logo = None
                brand.logo_storage_path = None
                brand.updated_by = request.user
                brand.save()

                return Response(
                    {"message": "Brand logo deleted successfully"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Failed to delete logo from storage"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(f"Error deleting brand logo: {str(e)}")
            return Response(
                {"error": f"Failed to delete logo: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"])
    def search(self, request):
        """Search brands by name or description"""
        search_query = request.query_params.get("search", "")

        if not search_query:
            return Response(
                {"error": "Search query is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        brands = self.get_queryset().filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

        serializer = self.get_serializer(brands, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def active(self, request):
        """Get only active brands"""
        active_brands = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(active_brands, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def toggle_status(self, request, slug=None):
        """Toggle brand active status"""
        brand = self.get_object()

        # Check permissions
        if not (request.user.is_staff or request.user == brand.created_by):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        brand.is_active = not brand.is_active
        brand.updated_by = request.user
        brand.save()

        status_text = "activated" if brand.is_active else "deactivated"

        return Response(
            {
                "message": f"Brand '{brand.name}' {status_text} successfully",
                "is_active": brand.is_active,
            },
            status=status.HTTP_200_OK,
        )

    def list(self, request, *args, **kwargs):
        """Override list to add filtering options"""
        queryset = self.filter_queryset(self.get_queryset())

        # Filter by active status
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            is_active_bool = is_active.lower() == "true"
            queryset = queryset.filter(is_active=is_active_bool)

        # Search functionality
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to add additional data"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Add product count
        data = serializer.data
        data["total_products"] = instance.products.count()
        data["active_products"] = instance.products.filter(is_active=True).count()

        return Response(data)


class ProductAttributeViewSet(viewsets.ModelViewSet):
    queryset = ProductAttribute.objects.all()
    serializer_class = ProductAttributeSerializer
    # Adjust permission classes - temporarily relaxed for debugging
    permission_classes = [IsAuthenticated]  # Remove HasModulePermission temporarily

    def get_queryset(self):
        """
        Filter queryset based on user permissions:
        - Admins see all attributes
        - Sellers see only their product attributes
        - Others see only published product attributes
        """
        queryset = super().get_queryset()
        user = self.request.user

        # Query parameters
        product_slug = self.request.query_params.get("product_slug", None)
        attribute_type = self.request.query_params.get("attribute_type", None)

        # Apply specific filters if provided
        if product_slug:
            queryset = queryset.filter(product__slug=product_slug)
        if attribute_type:
            queryset = queryset.filter(attribute_type=attribute_type)

        # Filter based on user role
        if user.is_superuser or (hasattr(user, "is_admin") and user.is_admin):
            return queryset  # Admin sees all

        if hasattr(user, "has_module_permission") and user.has_module_permission(
            "products", "read"
        ):
            return queryset  # Users with specific permission see all

        # Sellers see only their product attributes
        return queryset.filter(product__seller=user)

    def perform_create(self, serializer):
        """Validate user can create attribute for this product"""
        product_id = self.request.data.get("product")

        if not product_id:
            raise ValidationError({"product": "Product ID is required"})

        try:
            product = Product.objects.get(id=product_id)

            # Debug information
            print(f"User attempting to create attribute: {self.request.user}")
            print(f"Product seller: {product.seller}")
            print(f"Is superuser: {self.request.user.is_superuser}")
            print(f"User == seller: {self.request.user == product.seller}")

            # Check if user is the product owner or has admin rights
            if self.request.user.is_superuser or self.request.user == product.seller:
                # Add product to serializer data and save
                serializer.save(product=product)
            else:
                raise PermissionDenied(
                    f"You don't have permission to add attributes to this product (ID: {product_id})"
                )
        except Product.DoesNotExist:
            raise NotFound(f"Product with ID {product_id} not found")


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product variants (color/size combinations)
    Complete CRUD operations for variants
    """

    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantDetailSerializer
    permission_classes = [IsAuthenticated]  # Simplified permissions
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["sku", "product__name"]
    ordering_fields = ["product__name", "stock_quantity", "is_active"]

    def get_permissions(self):
        """
        Custom permission handling:
        - Allow anyone to view variant details
        - Require authentication for modifications
        """
        if self.action in ["list", "retrieve", "get_by_product", "get_by_attributes"]:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]  # Removed HasModulePermission
        return [permission() for permission in permission_classes]

    def check_variant_permission(self, request, variant):
        """
        Helper method to check if user can modify this variant
        """
        user = request.user
        product = variant.product

        # Debug logging
        print(f"=== PERMISSION CHECK DEBUG ===")
        print(f"User: {user} (ID: {user.id})")
        print(f"Product seller: {product.seller} (ID: {product.seller.id})")
        print(f"Is staff: {user.is_staff}")
        print(f"Is superuser: {user.is_superuser}")
        print(f"User == Seller: {user == product.seller}")
        print(f"User ID == Seller ID: {user.id == product.seller.id}")

        # Allow staff/superuser
        if user.is_staff or user.is_superuser:
            print("✓ Permission granted: User is staff/superuser")
            return True

        # Check if user owns the product
        if user == product.seller:
            print("✓ Permission granted: User is product seller (object comparison)")
            return True

        # Check by ID comparison (fallback)
        if user.id == product.seller.id:
            print("✓ Permission granted: User is product seller (ID comparison)")
            return True

        # Check if user has seller profile and it matches
        if hasattr(user, "seller_profile") and user.seller_profile:
            if user.seller_profile == product.seller:
                print("✓ Permission granted: User seller profile matches")
                return True

        print("✗ Permission denied: No matching criteria")
        return False

    def get_queryset(self):
        """
        Filter variants based on user permissions:
        - Admins/staff see all variants
        - Sellers see only their product variants
        - Others see only active variants
        """
        queryset = super().get_queryset()
        user = self.request.user

        # Anonymous users see only active variants of active products
        if not user.is_authenticated:
            return queryset.filter(
                is_active=True, product__is_active=True, product__status="published"
            )

        # Superusers and admins can see all variants
        if user.is_superuser or (hasattr(user, "is_admin") and user.is_admin):
            return queryset

        # Staff users can see all variants
        if user.is_staff:
            return queryset

        # Sellers see only their product variants
        return queryset.filter(product__seller=user)

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action
        """
        if self.action in ["list", "get_by_product"]:
            return ProductVariantSerializer
        return ProductVariantDetailSerializer

    # ===== STANDARD CRUD OPERATIONS =====

    def list(self, request, *args, **kwargs):
        """
        List all variants with pagination and filtering
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Optional product filtering
        product_id = request.query_params.get("product_id")
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # Optional active filtering
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Get individual variant details
        """
        try:
            variant = self.get_object()
            serializer = self.get_serializer(variant)
            return Response(serializer.data)
        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def create(self, request, *args, **kwargs):
        """
        Create a new variant
        """
        # Get product ID from request
        product_id = request.data.get("product")
        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Create a dummy variant object for permission check
        dummy_variant = type("obj", (object,), {"product": product})()

        # Check permissions using helper method
        if not self.check_variant_permission(request, dummy_variant):
            return Response(
                {
                    "error": "You don't have permission to create variants for this product",
                    "debug": {
                        "user_id": request.user.id,
                        "seller_id": product.seller.id,
                        "user_is_staff": request.user.is_staff,
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Generate unique SKU if not provided
        if not request.data.get("sku"):
            import uuid

            request.data["sku"] = f"{product.sku}-{uuid.uuid4().hex[:6]}"

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            variant = serializer.save(product=product)

            # Handle attributes
            attributes_data = request.data.get("attributes", [])
            for attr_data in attributes_data:
                VariantAttribute.objects.create(
                    variant=variant,
                    attribute_type=attr_data.get("attribute_type"),
                    value=attr_data.get("value"),
                    display_value=attr_data.get("display_value"),
                )

            return Response(
                ProductVariantDetailSerializer(variant).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """
        Update entire variant (PUT) - Fixed with better permission checking
        """
        try:
            variant = self.get_object()

            # Use helper method for permission check
            if not self.check_variant_permission(request, variant):
                return Response(
                    {
                        "error": "You don't have permission to update this variant",
                        "debug": {
                            "user_id": request.user.id,
                            "seller_id": variant.product.seller.id,
                            "user_is_staff": request.user.is_staff,
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(variant, data=request.data, partial=False)

            if serializer.is_valid():
                updated_variant = serializer.save()

                # Handle attributes update if provided
                if "attributes" in request.data:
                    # Delete existing attributes
                    variant.variant_attributes.all().delete()

                    # Create new attributes
                    for attr_data in request.data["attributes"]:
                        VariantAttribute.objects.create(
                            variant=updated_variant,
                            attribute_type=attr_data.get("attribute_type"),
                            value=attr_data.get("value"),
                            display_value=attr_data.get("display_value"),
                        )

                return Response(ProductVariantDetailSerializer(updated_variant).data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in variant update: {str(e)}")
            return Response(
                {"error": f"Update failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, pk=None):
        """
        Partially update variant (PATCH) - Fixed with better permission checking
        """
        try:
            variant = self.get_object()

            # Use helper method for permission check
            if not self.check_variant_permission(request, variant):
                return Response(
                    {
                        "error": "You don't have permission to update this variant",
                        "debug": {
                            "user_id": request.user.id,
                            "seller_id": variant.product.seller.id,
                            "user_is_staff": request.user.is_staff,
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = self.get_serializer(variant, data=request.data, partial=True)

            if serializer.is_valid():
                updated_variant = serializer.save()

                # Handle attributes update if provided
                if "attributes" in request.data:
                    # Delete existing attributes
                    variant.variant_attributes.all().delete()

                    # Create new attributes
                    for attr_data in request.data["attributes"]:
                        VariantAttribute.objects.create(
                            variant=updated_variant,
                            attribute_type=attr_data.get("attribute_type"),
                            value=attr_data.get("value"),
                            display_value=attr_data.get("display_value"),
                        )

                return Response(ProductVariantDetailSerializer(updated_variant).data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, pk=None):
        """
        Delete variant - Fixed with better permission checking
        """
        try:
            variant = self.get_object()

            # Use helper method for permission check
            if not self.check_variant_permission(request, variant):
                return Response(
                    {"error": "You don't have permission to delete this variant"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            variant_sku = variant.sku
            variant.delete()

            return Response(
                {"message": f"Variant {variant_sku} deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )

    # ===== CUSTOM ACTIONS =====

    @action(detail=False, methods=["GET"])
    def get_by_product(self, request):
        """
        Get all variants for a specific product
        """
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

        variants = self.get_queryset().filter(product=product)

        # Apply additional filters if provided
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            is_active = is_active.lower() == "true"
            variants = variants.filter(is_active=is_active)

        serializer = self.get_serializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    def get_by_attributes(self, request):
        """
        Get variants by attribute combinations (e.g., color and size)
        """
        product_id = request.query_params.get("product_id")
        color = request.query_params.get("color")
        size = request.query_params.get("size")

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
            )

        variants = self.get_queryset().filter(product=product, is_active=True)

        # Apply color filter if provided
        if color:
            variants = variants.filter(
                variant_attributes__attribute_type="color",
                variant_attributes__value=color,
            )

        # Apply size filter if provided
        if size:
            variants = variants.filter(
                variant_attributes__attribute_type="size",
                variant_attributes__value=size,
            )

        serializer = self.get_serializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["PATCH"])
    def update_stock(self, request, pk=None):
        """
        Update stock quantity for a specific variant - Fixed permission checking
        """
        try:
            variant = self.get_object()

            # Use helper method for permission check
            if not self.check_variant_permission(request, variant):
                return Response(
                    {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
                )

            # Get new stock quantity
            new_stock = request.data.get("stock_quantity")
            quantity_change = request.data.get("quantity_change")

            if new_stock is not None:
                # Direct stock update
                try:
                    new_stock = int(new_stock)
                    if new_stock < 0:
                        return Response(
                            {"error": "Stock quantity cannot be negative"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    variant.stock_quantity = new_stock
                    variant.save()

                    return Response(
                        {
                            "message": "Stock updated successfully",
                            "variant_id": variant.id,
                            "sku": variant.sku,
                            "new_stock": variant.stock_quantity,
                        }
                    )

                except ValueError:
                    return Response(
                        {"error": "Invalid stock quantity format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif quantity_change is not None:
                # Relative stock change
                try:
                    quantity_change = int(quantity_change)
                    variant.update_stock(quantity_change)

                    return Response(
                        {
                            "message": "Stock updated successfully",
                            "variant_id": variant.id,
                            "sku": variant.sku,
                            "new_stock": variant.stock_quantity,
                        }
                    )
                except ValidationError as e:
                    return Response(
                        {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid quantity change format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {
                        "error": "Either 'stock_quantity' or 'quantity_change' is required"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["POST"])
    def bulk_update_stock(self, request):
        """
        Bulk update stock quantities for multiple variants - Fixed permission checking
        """
        updates = request.data.get("updates", [])
        if not updates:
            return Response(
                {"error": "No updates provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        results = []
        errors = []

        with transaction.atomic():
            for update in updates:
                variant_id = update.get("variant_id")
                new_stock = update.get("stock_quantity")
                quantity_change = update.get("quantity_change")

                if not variant_id:
                    errors.append(
                        {"variant_id": variant_id, "error": "variant_id is required"}
                    )
                    continue

                if new_stock is None and quantity_change is None:
                    errors.append(
                        {
                            "variant_id": variant_id,
                            "error": "Either stock_quantity or quantity_change is required",
                        }
                    )
                    continue

                try:
                    variant = ProductVariant.objects.get(id=variant_id)

                    # Use helper method for permission check
                    if not self.check_variant_permission(request, variant):
                        errors.append(
                            {
                                "variant_id": variant_id,
                                "error": "You do not have permission to update this variant",
                            }
                        )
                        continue

                    if new_stock is not None:
                        # Direct stock update
                        new_stock = int(new_stock)
                        if new_stock < 0:
                            errors.append(
                                {
                                    "variant_id": variant_id,
                                    "error": "Stock quantity cannot be negative",
                                }
                            )
                            continue

                        variant.stock_quantity = new_stock
                        variant.save()
                    else:
                        # Relative stock change
                        quantity_change = int(quantity_change)
                        variant.update_stock(quantity_change)

                    results.append(
                        {
                            "variant_id": variant_id,
                            "sku": variant.sku,
                            "new_stock": variant.stock_quantity,
                        }
                    )

                except ProductVariant.DoesNotExist:
                    errors.append(
                        {"variant_id": variant_id, "error": "Variant not found"}
                    )
                except ValidationError as e:
                    errors.append({"variant_id": variant_id, "error": str(e)})
                except ValueError as e:
                    errors.append(
                        {
                            "variant_id": variant_id,
                            "error": f"Invalid number format: {str(e)}",
                        }
                    )
                except Exception as e:
                    errors.append(
                        {
                            "variant_id": variant_id,
                            "error": f"Failed to update stock: {str(e)}",
                        }
                    )

        return Response(
            {
                "success": len(results),
                "failures": len(errors),
                "results": results,
                "errors": errors,
            }
        )

    @action(detail=True, methods=["POST"])
    def toggle_active(self, request, pk=None):
        """
        Toggle variant active status - Fixed permission checking
        """
        try:
            variant = self.get_object()

            # Use helper method for permission check
            if not self.check_variant_permission(request, variant):
                return Response(
                    {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
                )

            variant.is_active = not variant.is_active
            variant.save()

            return Response(
                {
                    "message": f"Variant {'activated' if variant.is_active else 'deactivated'} successfully",
                    "variant_id": variant.id,
                    "sku": variant.sku,
                    "is_active": variant.is_active,
                }
            )

        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["GET"])
    def stock_history(self, request, pk=None):
        """
        Get stock change history for a variant (if you have stock history tracking)
        """
        try:
            variant = self.get_object()

            # This would require a StockHistory model - placeholder for now
            return Response(
                {
                    "variant_id": variant.id,
                    "sku": variant.sku,
                    "current_stock": variant.stock_quantity,
                    "message": "Stock history tracking not implemented yet",
                }
            )

        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )

    # Add a debug endpoint for troubleshooting
    @action(detail=True, methods=["GET"])
    def debug_permissions(self, request, pk=None):
        """
        Debug endpoint to check permissions for a variant
        """
        try:
            variant = self.get_object()
            has_permission = self.check_variant_permission(request, variant)

            return Response(
                {
                    "variant_id": variant.id,
                    "sku": variant.sku,
                    "user_id": request.user.id,
                    "user_email": request.user.email,
                    "product_seller_id": variant.product.seller.id,
                    "product_seller_email": variant.product.seller.email,
                    "user_is_staff": request.user.is_staff,
                    "user_is_superuser": request.user.is_superuser,
                    "has_permission": has_permission,
                    "user_equals_seller": request.user == variant.product.seller,
                    "user_id_equals_seller_id": request.user.id
                    == variant.product.seller.id,
                }
            )
        except ProductVariant.DoesNotExist:
            return Response(
                {"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND
            )


class ProductFeatureRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product feature requests from sellers to admins
    """

    serializer_class = ProductFeatureRequestSerializer
    permission_classes = [IsAuthenticated, HasModulePermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["product__name", "reason", "contact_name", "contact_email"]
    ordering_fields = ["created_at", "product__name", "status"]

    def get_queryset(self):
        """
        Get queryset based on user role:
        - Admins can see all requests
        - Sellers can only see their own requests
        """
        user = self.request.user

        # For admins and superusers, show all requests
        if user.is_superuser or (hasattr(user, "is_admin") and user.is_admin):
            return ProductFeatureRequest.objects.all().select_related(
                "product", "requested_by", "reviewed_by"
            )

        # For sellers and other users, only show their own requests
        return ProductFeatureRequest.objects.filter(requested_by=user).select_related(
            "product", "requested_by", "reviewed_by"
        )

    def perform_create(self, serializer):
        """
        Set requested_by to current user when creating a feature request
        """
        serializer.save(requested_by=self.request.user)

    @action(
        detail=True,
        methods=["POST"],
        permission_classes=[IsAuthenticated, HasModulePermission],
    )
    def approve(self, request, pk=None):
        """
        Approve a product feature request and mark the product as featured
        """
        feature_request = self.get_object()

        # Check if request is already processed
        if feature_request.status != "pending":
            return Response(
                {"error": f"Request already {feature_request.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user has admin permissions
        if not (
            request.user.is_superuser
            or (hasattr(request.user, "is_admin") and request.user.is_admin)
        ):
            return Response(
                {"error": "You do not have permission to approve feature requests"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Approve the request (this also updates the product)
            feature_request.approve(
                admin_user=request.user, admin_notes=request.data.get("admin_notes", "")
            )

            # Return the updated request
            serializer = self.get_serializer(feature_request)

            return Response(
                {
                    "message": "Product feature request approved",
                    "request": serializer.data,
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to approve request: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        methods=["POST"],
        permission_classes=[IsAuthenticated, HasModulePermission],
    )
    def reject(self, request, pk=None):
        """
        Reject a product feature request
        """
        feature_request = self.get_object()

        # Check if request is already processed
        if feature_request.status != "pending":
            return Response(
                {"error": f"Request already {feature_request.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user has admin permissions
        if not (
            request.user.is_superuser
            or (hasattr(request.user, "is_admin") and request.user.is_admin)
        ):
            return Response(
                {"error": "You do not have permission to reject feature requests"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Reject the request
            feature_request.reject(
                admin_user=request.user, admin_notes=request.data.get("admin_notes", "")
            )

            # Return the updated request
            serializer = self.get_serializer(feature_request)

            return Response(
                {
                    "message": "Product feature request rejected",
                    "request": serializer.data,
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to reject request: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_primary_image(request, slug):
    """Set an image as the primary image for the product"""
    try:
        product = get_object_or_404(Product, slug=slug)

        # Check permissions
        if not (request.user.is_staff or request.user == product.seller):
            return Response(
                {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
            )

        # Get image ID from request
        image_id = request.data.get("image_id")
        if not image_id:
            return Response(
                {"error": "Image ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get the image to set as primary
        try:
            image = ProductImage.objects.get(id=image_id, product=product)
        except ProductImage.DoesNotExist:
            return Response(
                {"error": "Image not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Update primary flag
        with transaction.atomic():
            # Set all images of this product to not primary
            ProductImage.objects.filter(product=product).update(is_primary=False)
            # Set the selected image as primary
            image.is_primary = True
            image.save()

        return Response(
            {"message": "Primary image set successfully"}, status=status.HTTP_200_OK
        )
    except Exception as e:
        import traceback

        print(f"Error setting primary image: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {"error": f"Failed to set primary image: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def hsn_code_list(request):
    """Get HSN codes with optional search filtering"""
    search_term = request.query_params.get("search", "")

    # Use raw SQL for direct access to tax_codes table
    with connection.cursor() as cursor:
        if search_term:
            cursor.execute(
                "SELECT code, description FROM tax_codes WHERE code_type = %s AND (code LIKE %s OR description LIKE %s) LIMIT 100",
                ["HSN", f"%{search_term}%", f"%{search_term}%"],
            )
        else:
            cursor.execute(
                "SELECT code, description FROM tax_codes WHERE code_type = %s LIMIT 100",
                ["HSN"],
            )

        results = cursor.fetchall()

    # Format results as list of dictionaries
    codes = [{"code": row[0], "description": row[1]} for row in results]

    return Response(codes)


@api_view(["GET"])
@permission_classes([AllowAny])
def sac_code_list(request):
    """Get SAC codes with search filtering"""
    search_term = request.query_params.get("search", "")

    # Use raw SQL for direct access to tax_codes table
    with connection.cursor() as cursor:
        if search_term:
            cursor.execute(
                "SELECT code, description FROM tax_codes WHERE code_type = %s AND (code LIKE %s OR description LIKE %s) LIMIT 100",
                ["SAC", f"%{search_term}%", f"%{search_term}%"],
            )
        else:
            cursor.execute(
                "SELECT code, description FROM tax_codes WHERE code_type = %s LIMIT 100",
                ["SAC"],
            )

        results = cursor.fetchall()

    # Format results as list of dictionaries
    codes = [{"code": row[0], "description": row[1]} for row in results]

    return Response(codes)


@api_view(["GET"])
def product_detail(request, pk=None, slug=None):
    """Get detailed product information by ID or slug"""
    try:
        if pk:
            product = get_object_or_404(Product, pk=pk)
        elif slug:
            product = get_object_or_404(Product, slug=slug)
        else:
            return Response({"error": "No identifier provided"}, status=400)

        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)
    except Exception as e:
        import traceback

        print("Error in product_detail:", str(e))
        print(traceback.format_exc())
        return Response({"error": str(e)}, status=500)


# Add or enhance this view in your views.py file


@action(detail=True, methods=["POST"])
def upload_images(self, request, slug=None):
    """
    Upload multiple product images with proper error handling and response
    """
    product = get_object_or_404(Product, slug=slug)

    if not (request.user.is_staff or request.user == product.seller):
        return Response(
            {"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN
        )

    images = request.FILES.getlist("images")
    if not images:
        return Response(
            {"error": "No images provided"}, status=status.HTTP_400_BAD_REQUEST
        )

    logger.info(
        f"Received {len(images)} images for product {product.id} ({product.name})"
    )

    image_service = ImageService()
    uploaded_images = []

    # Track whether this is the first image (to potentially set as primary)
    should_set_primary = request.data.get("is_primary") == "true"
    is_first_image = True

    for index, image in enumerate(images):
        try:
            # Extract original filename if available
            original_filename = ""
            if hasattr(image, "name"):
                original_filename = os.path.splitext(image.name)[0]
                original_filename = re.sub(r"[^a-zA-Z0-9_]", "_", original_filename)

            # Generate a unique identifier for each image
            unique_id = uuid.uuid4().hex[:8]
            timestamp = int(time.time())

            # Create a unique name for each image
            custom_name = f"{product.name}_{original_filename if original_filename else 'image'}_{index+1}_{timestamp}_{unique_id}"

            logger.info(f"Processing image {index+1}/{len(images)}: {custom_name}")

            # Upload with unique identifier
            file_path, file_url = image_service.upload_image(
                image, str(product.id), custom_name
            )

            # Determine if this image should be primary
            is_primary = should_set_primary and is_first_image

            image_serializer = ProductImageSerializer(
                data={
                    "product": product.id,
                    "image_url": file_url,
                    "storage_path": file_path,
                    "alt_text": request.data.get("alt_text", ""),
                    "is_primary": is_primary,
                    "color_attribute": request.data.get("color_attribute", None),
                }
            )

            if image_serializer.is_valid():
                image_obj = image_serializer.save()
                uploaded_images.append(image_serializer.data)

                # If this was the first image and set as primary, update flag
                if is_primary:
                    is_first_image = False

                logger.info(
                    f"Successfully saved image {index+1} with ID {image_obj.id}"
                )
            else:
                logger.error(
                    f"Image serializer validation failed: {image_serializer.errors}"
                )
                return Response(
                    image_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Error uploading image {index+1}: {str(e)}")
            return Response(
                {"error": f"Failed to upload image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return Response(
        {
            "message": f"Successfully uploaded {len(uploaded_images)} images",
            "images": uploaded_images,
        },
        status=status.HTTP_201_CREATED,
    )
