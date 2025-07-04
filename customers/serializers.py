# customers/serializers.py - Enhanced with product information

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Customer,
    Address,
    CartItem,
    WishlistItem,
    CustomerPreferences,
    CustomerActivity,
    CustomerTransaction,
    CustomerOrderStats,
)

User = get_user_model()


class ProductInfoSerializer(serializers.Serializer):
    """Serializer to include basic product information"""

    id = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    image = serializers.URLField(required=False, allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    sale_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    is_available = serializers.BooleanField(default=True)


class CartItemSerializer(serializers.ModelSerializer):
    total_price = serializers.SerializerMethodField()
    product_info = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product_id",
            "variant_id",
            "quantity",
            "price",
            "total_price",
            "product_info",
            "added_at",
            "updated_at",
        ]
        extra_kwargs = {"customer": {"read_only": True}}

    def get_total_price(self, obj):
        """Calculate total price for this item (quantity * price)"""
        return obj.quantity * obj.price

    def get_product_info(self, obj):
        """Get product information including slug"""
        try:
            # Import here to avoid circular imports
            from products.models import Product

            product = Product.objects.get(id=obj.product_id)
            return {
                "id": str(product.id),
                "name": product.name,
                "slug": product.slug,
                "image": (
                    product.featured_image
                    if hasattr(product, "featured_image")
                    else None
                ),
                "regular_price": (
                    product.regular_price if hasattr(product, "regular_price") else None
                ),
                "sale_price": (
                    product.sale_price if hasattr(product, "sale_price") else None
                ),
                "is_available": (
                    product.is_active if hasattr(product, "is_active") else True
                ),
            }
        except Exception as e:
            # Return basic info if product not found
            return {
                "id": obj.product_id,
                "name": "Product not found",
                "slug": "",
                "image": None,
                "regular_price": None,
                "sale_price": None,
                "is_available": False,
            }


class SessionCartItemSerializer(serializers.Serializer):
    """Serializer for session-based cart items"""

    id = serializers.CharField()
    product_id = serializers.CharField()
    variant_id = serializers.CharField(required=False, allow_null=True)
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_price = serializers.SerializerMethodField()
    product_info = serializers.SerializerMethodField()
    added_at = serializers.CharField()
    updated_at = serializers.CharField()

    def get_total_price(self, obj):
        """Calculate total price for this item"""
        return obj.get("quantity", 0) * obj.get("price", 0)

    def get_product_info(self, obj):
        """Get product information including slug"""
        try:
            # Import here to avoid circular imports
            from products.models import Product

            product = Product.objects.get(id=obj["product_id"])
            return {
                "id": str(product.id),
                "name": product.name,
                "slug": product.slug,
                "image": (
                    product.featured_image
                    if hasattr(product, "featured_image")
                    else None
                ),
                "regular_price": (
                    product.regular_price if hasattr(product, "regular_price") else None
                ),
                "sale_price": (
                    product.sale_price if hasattr(product, "sale_price") else None
                ),
                "is_available": (
                    product.is_active if hasattr(product, "is_active") else True
                ),
            }
        except Exception as e:
            # Return basic info if product not found
            return {
                "id": obj["product_id"],
                "name": "Product not found",
                "slug": "",
                "image": None,
                "regular_price": None,
                "sale_price": None,
                "is_available": False,
            }


class WishlistItemSerializer(serializers.ModelSerializer):
    product_info = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = [
            "id",
            "product_id",
            "variant_id",
            "product_info",
            "added_at",
        ]
        extra_kwargs = {"customer": {"read_only": True}}

    def get_product_info(self, obj):
        """Get product information including slug"""
        try:
            # Import here to avoid circular imports
            from products.models import Product

            product = Product.objects.get(id=obj.product_id)
            return {
                "id": str(product.id),
                "name": product.name,
                "slug": product.slug,
                "image": (
                    product.featured_image
                    if hasattr(product, "featured_image")
                    else None
                ),
                "regular_price": (
                    product.regular_price if hasattr(product, "regular_price") else None
                ),
                "sale_price": (
                    product.sale_price if hasattr(product, "sale_price") else None
                ),
                "is_available": (
                    product.is_active if hasattr(product, "is_active") else True
                ),
            }
        except Exception as e:
            # Return basic info if product not found
            return {
                "id": obj.product_id,
                "name": "Product not found",
                "slug": "",
                "image": None,
                "regular_price": None,
                "sale_price": None,
                "is_available": False,
            }


class SessionWishlistItemSerializer(serializers.Serializer):
    """Serializer for session-based wishlist items"""

    id = serializers.CharField()
    product_id = serializers.CharField()
    variant_id = serializers.CharField(required=False, allow_null=True)
    product_info = serializers.SerializerMethodField()
    added_at = serializers.CharField()

    def get_product_info(self, obj):
        """Get product information including slug"""
        try:
            # Import here to avoid circular imports
            from products.models import Product

            product = Product.objects.get(id=obj["product_id"])
            return {
                "id": str(product.id),
                "name": product.name,
                "slug": product.slug,
                "image": (
                    product.featured_image
                    if hasattr(product, "featured_image")
                    else None
                ),
                "regular_price": (
                    product.regular_price if hasattr(product, "regular_price") else None
                ),
                "sale_price": (
                    product.sale_price if hasattr(product, "sale_price") else None
                ),
                "is_available": (
                    product.is_active if hasattr(product, "is_active") else True
                ),
            }
        except Exception as e:
            # Return basic info if product not found
            return {
                "id": obj["product_id"],
                "name": "Product not found",
                "slug": "",
                "image": None,
                "regular_price": None,
                "sale_price": None,
                "is_available": False,
            }


# Keep all other existing serializers unchanged
class ContactUSSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField()
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField()


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"
        extra_kwargs = {"customer": {"read_only": True}}


class CartItemCreateSerializer(serializers.Serializer):
    """Serializer for creating a cart item"""

    product_id = serializers.CharField(required=True)
    variant_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class CartItemUpdateSerializer(serializers.Serializer):
    """Serializer for updating a cart item"""

    quantity = serializers.IntegerField(min_value=0, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def validate_quantity(self, value):
        """Validate quantity - if 0, the item will be removed"""
        return value


class CartBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating cart items"""

    items = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(required=False), allow_empty=False
        )
    )

    def validate_items(self, value):
        """Validate items format"""
        for item in value:
            if "product_id" not in item:
                raise serializers.ValidationError(
                    "product_id is required for each item"
                )
            if "quantity" not in item:
                raise serializers.ValidationError("quantity is required for each item")
            try:
                quantity = int(item["quantity"])
                if quantity < 0:
                    raise serializers.ValidationError(
                        "quantity must be a positive integer"
                    )
            except (ValueError, TypeError):
                raise serializers.ValidationError("quantity must be a valid integer")
        return value


class CartSummarySerializer(serializers.Serializer):
    """Serializer for cart summary information"""

    total_items = serializers.IntegerField()
    item_count = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    items = serializers.ListField()  # Will be populated with appropriate serializer


class RemoveCartItemSerializer(serializers.Serializer):
    """Serializer for removing a product from the cart"""

    product_id = serializers.CharField(required=True)
    variant_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


# Keep all other existing serializers as they are...
class CustomerPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPreferences
        fields = "__all__"
        extra_kwargs = {"customer": {"read_only": True}}


class CustomerActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerActivity
        fields = "__all__"
        extra_kwargs = {"customer": {"read_only": True}}


class CustomerTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerTransaction
        fields = "__all__"
        extra_kwargs = {"customer": {"read_only": True}}


class CustomerOrderStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerOrderStats
        fields = "__all__"
        extra_kwargs = {"customer": {"read_only": True}}


class CustomerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone_number", read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    cart_items = CartItemSerializer(many=True, read_only=True)
    wishlist_items = WishlistItemSerializer(many=True, read_only=True)
    preferences = CustomerPreferencesSerializer(read_only=True)
    transactions = CustomerTransactionSerializer(many=True, read_only=True)
    activities = CustomerActivitySerializer(many=True, read_only=True)
    order_stats = CustomerOrderStatsSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "email",
            "phone",
            "full_name",
            "date_of_birth",
            "gender",
            "profile_picture",
            "status",
            "wallet_balance",
            "reward_points",
            "total_orders",
            "total_order_value",
            "addresses",
            "cart_items",
            "wishlist_items",
            "preferences",
            "transactions",
            "activities",
            "order_stats",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user"]


class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data.get("password") != data.get("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords do not match"})

        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({"email": "Email is already registered"})

        if User.objects.filter(phone_number=data["phone"]).exists():
            raise serializers.ValidationError(
                {"phone": "Phone number is already registered"}
            )

        return data


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class CustomerProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.ChoiceField(
        choices=["male", "female", "other"], required=False
    )
    profile_picture = serializers.URLField(required=False)

    def validate_gender(self, value):
        valid_choices = ["male", "female", "other"]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Gender must be one of: {', '.join(valid_choices)}"
            )
        return value


class AddressUpdateSerializer(serializers.Serializer):
    address_id = serializers.CharField(required=False)
    address_type = serializers.ChoiceField(choices=["home", "work", "other"])
    full_name = serializers.CharField()
    phone = serializers.CharField()
    street = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    country = serializers.CharField(default="India")
    pincode = serializers.CharField()
    is_default = serializers.BooleanField(default=False)


class CartUpdateSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    variant_id = serializers.CharField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1)


class BulkCartUpdateSerializer(serializers.Serializer):
    items = CartUpdateSerializer(many=True)


class PreferencesUpdateSerializer(serializers.Serializer):
    currency = serializers.CharField(max_length=5, required=False)
    language = serializers.CharField(max_length=5, required=False)
    notification_preferences = serializers.JSONField(required=False)
    marketing_preferences = serializers.JSONField(required=False)
