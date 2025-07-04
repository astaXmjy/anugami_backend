# serializers.py
# Combined implementation for Product serializers

from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from customers.models import WishlistItem

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
from system_users.models import CustomUser
from categories.models import Category
from .constants import COLORS, SIZE_CHOICES, AGE_GROUP_CHOICES, GENDER_CHOICES

from sellers.models import Seller


class SellerInfoSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(read_only=True)
    business_name = serializers.CharField(read_only=True)
    business_address = serializers.CharField(read_only=True)
    logo = serializers.ImageField(read_only=True)

    class Meta:
        model = Seller
        fields = [
            "id",
            "user_name",
            "email",
            "business_name",
            "business_address",
            "logo",
            "is_email_verified",
        ]
        read_only_fields = fields


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def create(self, validated_data):
        # Automatically generate slug from the name
        validated_data["slug"] = slugify(validated_data["name"])
        return super().create(validated_data)


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for ProductImage model."""

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "product",
            "image_url",
            "alt_text",
            "is_primary",
            "sort_order",
            "created_at",
            "storage_path",
            "color_attribute",
        ]
        read_only_fields = ["id", "created_at"]


class ProductVideoSerializer(serializers.ModelSerializer):
    """Serializer for ProductVideo model."""

    class Meta:
        model = ProductVideo
        fields = [
            "id",
            "product",
            "video_url",
            "title",
            "duration",
            "thumbnail_url",
            "is_featured",
            "sort_order",
            "created_at",
            "storage_path",
            "thumbnail_storage_path",
        ]
        read_only_fields = ["id", "created_at"]


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Serializer for ProductAttribute model."""

    available_values = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttribute
        fields = [
            "id",
            "product",
            "attribute_type",
            "name",
            "value",
            "display_value",
            "type",
            "is_visible",
            "is_variation",
            "is_searchable",
            "sort_order",
            "available_values",
        ]
        read_only_fields = ["id", "display_value"]

    def get_available_values(self, obj):
        """Get available values based on attribute type."""
        if obj.attribute_type == "size":
            return SIZE_CHOICES
        elif obj.attribute_type == "color":
            return COLORS
        elif obj.attribute_type == "age_group":
            return AGE_GROUP_CHOICES
        elif obj.attribute_type == "gender":
            return GENDER_CHOICES
        return []

    def validate(self, data):
        """Validate attribute values based on type."""
        attribute_type = data.get("attribute_type")
        value = data.get("value")

        validation_map = {
            "size": dict(SIZE_CHOICES),
            "color": dict(COLORS),
            "age_group": dict(AGE_GROUP_CHOICES),
            "gender": dict(GENDER_CHOICES),
        }

        if attribute_type in validation_map:
            valid_values = validation_map[attribute_type]
            if value not in valid_values:
                raise ValidationError(
                    {
                        "value": f"Invalid {attribute_type}. Must be one of: {', '.join(valid_values.keys())}"
                    }
                )

        return data


# Define these serializers first to avoid circular imports
class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for ProductReview model."""

    product = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.SerializerMethodField()

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

    def get_user(self, obj):
        """Get user details for the review"""
        if obj.user:
            return {
                "id": str(obj.user.id),
                "name": getattr(
                    obj.user,
                    "name",
                    obj.user.email.split("@")[0] if obj.user.email else "Anonymous",
                ),
                "email": obj.user.email,
                "avatar": None,  # Add avatar logic if you have user avatars
            }
        return None

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


class VariantAttributeSerializer(serializers.ModelSerializer):
    """Serializer for VariantAttribute model."""

    class Meta:
        model = VariantAttribute
        fields = ["id", "attribute_type", "value", "display_value"]
        read_only_fields = ["id", "display_value"]


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant model."""

    attributes = VariantAttributeSerializer(
        source="variant_attributes", many=True, read_only=True
    )
    price = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "stock_quantity",
            "price",
            "is_active",
            "attributes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_price(self, obj):
        return obj.get_price()


class ProductVariantDetailSerializer(ProductVariantSerializer):
    """Detailed serializer for ProductVariant model."""

    class Meta(ProductVariantSerializer.Meta):
        fields = ProductVariantSerializer.Meta.fields + [
            "price_adjustment",
            "has_custom_price",
            "custom_price",
            "product",
        ]


class ProductSerializer(serializers.ModelSerializer):
    """Base serializer for Product model"""

    brand_name = serializers.CharField(source="brand.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "sku",
            "description",
            "additional_description" "category",
            "category_name",
            "brand",
            "brand_name",
            "regular_price",
            "sale_price",
            "stock_quantity",
            "status",
            "is_active",
            "is_featured",
            "created_at",
            "updated_at",
            "primary_image",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_primary_image(self, obj):
        """Get the primary image URL for product thumbnail display"""
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            return primary_image.image_url
        # Return first image if no primary image is set
        first_image = obj.images.first()
        if first_image:
            return first_image.image_url
        return None


class ProductListSerializer(serializers.ModelSerializer):
    """List serializer for Product model."""

    brand = BrandSerializer(read_only=True)
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    seller_info = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()

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
            "primary_image",
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

    def get_primary_image(self, obj):
        """Get the primary image URL for product thumbnail display"""
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image:
            return primary_image.image_url
        # Return first image if no primary image is set
        first_image = obj.images.first()
        if first_image:
            return first_image.image_url
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Product model."""

    brand = BrandSerializer(read_only=True)
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    videos = ProductVideoSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(
        many=True, required=False
    )  # Changed to required=False for flexibility
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
            "additional_description",
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

    def update(self, instance, validated_data):
        """Handle product update including attributes"""
        # Extract attributes data if present
        attributes_data = validated_data.pop("attributes", None)

        # Update product fields
        instance = super().update(instance, validated_data)

        # Handle attributes update
        if attributes_data is not None:
            # Clear existing attributes
            instance.attributes.all().delete()

            # Create new attributes
            for attr_data in attributes_data:
                # Create the attribute with the product instance
                ProductAttribute.objects.create(
                    product=instance,
                    attribute_type=attr_data.get("attribute_type", "custom"),
                    name=attr_data.get("name"),
                    value=attr_data.get("value"),
                    display_value=attr_data.get(
                        "display_value", attr_data.get("value")
                    ),
                    type=attr_data.get("type", "text"),
                    is_visible=attr_data.get("is_visible", True),
                    is_variation=attr_data.get("is_variation", False),
                    is_searchable=attr_data.get("is_searchable", True),
                    sort_order=attr_data.get("sort_order", 0),
                )

        return instance

    def create(self, validated_data):
        """Handle product creation including attributes"""
        # Extract attributes data if present
        attributes_data = validated_data.pop("attributes", None)

        # Create the product
        product = super().create(validated_data)

        # Create attributes if provided
        if attributes_data:
            for attr_data in attributes_data:
                ProductAttribute.objects.create(
                    product=product,
                    attribute_type=attr_data.get("attribute_type", "custom"),
                    name=attr_data.get("name"),
                    value=attr_data.get("value"),
                    display_value=attr_data.get(
                        "display_value", attr_data.get("value")
                    ),
                    type=attr_data.get("type", "text"),
                    is_visible=attr_data.get("is_visible", True),
                    is_variation=attr_data.get("is_variation", False),
                    is_searchable=attr_data.get("is_searchable", True),
                    sort_order=attr_data.get("sort_order", 0),
                )

        return product


class ProductFeatureRequestSerializer(serializers.ModelSerializer):
    """Serializer for product feature requests"""

    product_details = ProductSerializer(source="product", read_only=True)
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


# Add these serializers to your serializers.py file


class ProductMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for Product model."""

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "regular_price", "sale_price"]


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


class MobileVariantOptionSerializer(serializers.Serializer):
    """Simplified variant data for mobile UI"""

    color_value = serializers.CharField()
    color_display = serializers.CharField()
    image_url = serializers.URLField(allow_null=True)
    available_sizes = serializers.ListField(child=serializers.DictField())
    has_stock = serializers.BooleanField()


class CartSerializer(serializers.Serializer):
    """
    Cart Serializer with Comprehensive Validation
    """

    class Meta:
        fields = ["id", "user", "items", "total_price"]

    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    items = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    def get_items(self, obj):
        """Get cart items with product details"""
        return CartItemDetailSerializer(obj.cartitem_set.all(), many=True).data

    def validate(self, data):
        """
        Validate cart items
        - Check product availability
        - Validate stock quantities
        """
        user = self.context.get("request").user

        # Perform comprehensive cart validation
        for item in data.get("items", []):
            product = item.get("product")
            quantity = item.get("quantity")

            # Check product availability
            if not product.is_active or product.status != "published":
                raise serializers.ValidationError(
                    f"Product {product.name} is not available"
                )

            # Validate stock
            if quantity > product.stock_quantity and not product.allow_backorder:
                raise serializers.ValidationError(
                    f"Insufficient stock for {product.name}"
                )

        return data


class CartItemDetailSerializer(serializers.Serializer):
    """
    Detailed Cart Item Serializer
    """

    class Meta:
        fields = ["product", "quantity", "subtotal"]

    product = ProductDetailSerializer(read_only=True)
    quantity = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)


# 4. Product comparison serializer (missing in your file)
class ProductComparisonSerializer(serializers.Serializer):
    """
    Serializer for Product Comparison
    """

    class Meta:
        fields = ["id", "name", "brand", "price", "attributes", "images"]

    id = serializers.UUIDField()
    name = serializers.CharField()
    brand = BrandSerializer(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)


# 5. Order-related serializers (missing in your file)
class OrderItemSerializer(serializers.Serializer):
    """Serializer for Order Items"""

    product = ProductMinimalSerializer(read_only=True)
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    def validate(self, data):
        """Calculate subtotal"""
        data["subtotal"] = data["quantity"] * data["price"]
        return data


class OrderSerializer(serializers.Serializer):
    """Serializer for Orders"""

    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    items = OrderItemSerializer(many=True)
    total_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    status = serializers.ChoiceField(
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )
    created_at = serializers.DateTimeField(read_only=True)

    def validate(self, data):
        """Validate order items and calculate total"""
        items = data.get("items", [])
        total_amount = sum(item["quantity"] * item["price"] for item in items)
        data["total_amount"] = total_amount
        return data


# 6. Address and payment serializers (missing in your file)
class ShippingAddressSerializer(serializers.Serializer):
    """Serializer for Shipping Addresses"""

    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    full_name = serializers.CharField(max_length=255)
    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    phone_number = serializers.CharField(max_length=20)
    is_default = serializers.BooleanField(default=False)

    def validate_postal_code(self, value):
        """Basic postal code validation"""
        # Add more specific validation as needed
        if not value.isalnum():
            raise ValidationError("Invalid postal code format")
        return value


class PaymentMethodSerializer(serializers.Serializer):
    """Serializer for Payment Methods"""

    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    card_type = serializers.ChoiceField(
        choices=[
            ("visa", "Visa"),
            ("mastercard", "Mastercard"),
            ("amex", "American Express"),
            ("discover", "Discover"),
        ]
    )
    last_four_digits = serializers.CharField(max_length=4)
    expiry_month = serializers.IntegerField(min_value=1, max_value=12)
    expiry_year = serializers.IntegerField(min_value=2023, max_value=2040)
    is_default = serializers.BooleanField(default=False)

    def validate(self, data):
        """Validate card expiry"""
        from datetime import datetime

        current_year = datetime.now().year
        current_month = datetime.now().month

        if data["expiry_year"] < current_year or (
            data["expiry_year"] == current_year and data["expiry_month"] < current_month
        ):
            raise ValidationError("Card has expired")

        return data


# 7. Recently viewed products serializer (missing in your file)
class RecentlyViewedProductSerializer(serializers.ModelSerializer):
    product = ProductMinimalSerializer(read_only=True)
    variant_details = serializers.SerializerMethodField()

    class Meta:
        model = RecentlyViewedProduct
        fields = ["id", "product", "variant_details", "viewed_at"]

    def get_variant_details(self, obj):
        if obj.variant:
            return {
                "id": obj.variant.id,
                "attributes": VariantAttributeSerializer(
                    obj.variant.variant_attributes.all(), many=True
                ).data,
            }
        return None


class ProductRecommendationSerializer(serializers.Serializer):
    """Serializer for product recommendations"""

    recommended_products = ProductMinimalSerializer(many=True, read_only=True)
    recommendation_type = serializers.CharField()
    title = serializers.CharField()
