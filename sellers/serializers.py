# sellers/serializers.py
from rest_framework import serializers
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.conf import settings
import os
from .models import Seller, ShippingLocation, Order, OrderItem


class BaseSellerSerializer(serializers.ModelSerializer):
    """Base serializer with common validations"""

    # Phone number validation
    phone = serializers.CharField(
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$", message="Enter a valid phone number"
            )
        ]
    )

    # Email validation
    email = serializers.EmailField()

    class Meta:
        model = Seller
        abstract = True

    def validate_pan_number(self, value):
        """PAN Number validation"""
        if not value or len(value) != 10:
            raise serializers.ValidationError("PAN number must be 10 characters long")

        # Regex for PAN number format
        import re

        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", value):
            raise serializers.ValidationError("Invalid PAN number format")

        return value

    def validate_gst_number(self, value):
        """GST Number validation"""
        if not value or len(value) != 15:
            raise serializers.ValidationError("GST number must be 15 characters long")

        # Basic GST number validation
        import re

        if not re.match(
            r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", value
        ):
            raise serializers.ValidationError("Invalid GST number format")

        return value


class SellerRegistrationSerializer(BaseSellerSerializer):
    """Serializer for seller initial registration with PAN card upload"""

    # Password field (write-only)
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        error_messages={"min_length": "Password must be at least 8 characters long"},
    )

    # Confirm password field
    confirm_password = serializers.CharField(write_only=True, required=True)

    # Add PAN card upload field
    pan_card_image = serializers.FileField(
        required=True, error_messages={"required": "PAN card image is required"}
    )

    class Meta:
        model = Seller
        fields = [
            "full_name",
            "email",
            "phone",
            "business_name",
            "business_address",
            "gst_number",
            "pan_number",
            "pan_card_image",  # Added PAN card image field
            "password",
            "confirm_password",
            "account_name",
            "account_number",
            "ifsc_code",
            "bank_name",
        ]
        extra_kwargs = {
            "business_address": {"required": False},
            "gst_number": {"required": False},
            "pan_number": {"required": True},
            "account_name": {"required": False},
            "account_number": {"required": False},
            "ifsc_code": {"required": False},
            "bank_name": {"required": False},  # Made PAN number required
        }

    def validate_pan_card_image(self, value):
        """Validate PAN card image"""
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 5MB")

        # Check file extension
        import os

        ext = os.path.splitext(value.name)[1].lower()
        allowed_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )

        return value

    def validate(self, data):
        """
        Cross-field validation
        """
        # Check password match
        if data.get("password") != data.get("confirm_password"):
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )

        # Check if email already exists
        if Seller.objects.filter(email=data.get("email")).exists():
            raise serializers.ValidationError(
                {"email": "This email is already registered"}
            )

        # Check if phone already exists
        if Seller.objects.filter(phone=data.get("phone")).exists():
            raise serializers.ValidationError(
                {"phone": "This phone number is already registered"}
            )

        # Check PAN number format
        pan_number = data.get("pan_number")
        if pan_number:
            import re

            if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan_number):
                raise serializers.ValidationError(
                    {
                        "pan_number": "Invalid PAN number format. It should be in the format AAAAA0000A"
                    }
                )

        return data

    def create(self, validated_data):
        """
        Remove confirm_password and handle PAN card upload before creating
        """
        validated_data.pop("confirm_password")
        pan_card_image = validated_data.pop("pan_card_image")

        # Create seller
        seller = super().create(validated_data)

        # Upload PAN card to Firebase
        try:
            document_service = DocumentUploadService()
            pan_url = document_service.upload_pan_to_firebase(pan_card_image, seller.id)

            # Save PAN card URL
            seller.pan_document_url = pan_url
            seller.save()
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"PAN Card Upload Error: {str(e)}")

        return seller


class DocumentUploadSerializer(serializers.Serializer):
    """
    Serializer for document upload
    """

    gst_document = serializers.FileField(
        required=False,
        validators=[
            # Add file type and size validators
        ],
    )
    pan_document = serializers.FileField(
        required=False,
        validators=[
            # Add file type and size validators
        ],
    )
    bank_proof = serializers.FileField(
        required=False,
        validators=[
            # Add file type and size validators
        ],
    )

    def validate(self, data):
        """
        Validate document uploads
        """
        # Ensure at least one document is uploaded
        if not any(data.values()):
            raise serializers.ValidationError("At least one document must be uploaded")

        # Add custom validation for each document type
        for doc_type, doc_file in data.items():
            if doc_file:
                # Validate file size (e.g., max 5MB)
                if doc_file.size > 5 * 1024 * 1024:
                    raise serializers.ValidationError(
                        {doc_type: "File size must be less than 5MB"}
                    )

                # Validate file type
                allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png"]
                ext = os.path.splitext(doc_file.name)[1].lower()
                if ext not in allowed_extensions:
                    raise serializers.ValidationError(
                        {
                            doc_type: f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
                        }
                    )

        return data


class SellerProfileUpdateSerializer(BaseSellerSerializer):
    """
    Serializer for updating seller profile
    """

    class Meta:
        model = Seller
        fields = [
            "full_name",
            "business_name",
            "business_address",
            "account_name",
            "account_number",
            "ifsc_code",
            "bank_name",
        ]
        extra_kwargs = {
            "full_name": {"required": False},
            "business_name": {"required": False},
            "business_address": {"required": False},
            "account_name": {"required": False},
            "account_number": {"required": False},
            "ifsc_code": {"required": False},
            "bank_name": {"required": False},
        }

    def validate_account_number(self, value):
        """
        Bank account number validation
        """
        if value:
            # Remove any spaces or dashes
            value = "".join(filter(str.isdigit, value))

            # Check length (typical Indian bank account)
            if len(value) < 9 or len(value) > 18:
                raise serializers.ValidationError("Invalid bank account number")

        return value

    def validate_ifsc_code(self, value):
        """
        IFSC Code validation
        """
        if value:
            # Regex for IFSC code
            import re

            if not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", value):
                raise serializers.ValidationError("Invalid IFSC code format")

        return value


class SellerSerializer(BaseSellerSerializer):
    """Serializer for Seller model"""

    # Add pan_document_url field
    pan_document_url = serializers.URLField(read_only=True)

    # Add bank details fields explicitly
    account_name = serializers.CharField(read_only=True)
    account_number = serializers.CharField(read_only=True)
    ifsc_code = serializers.CharField(read_only=True)
    bank_name = serializers.CharField(read_only=True)

    class Meta:
        model = Seller
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "business_name",
            "business_address",
            "gst_number",
            "pan_number",
            "pan_document_url",  # Added pan_document_url
            # Bank Details - ADD THESE FIELDS
            "account_name",
            "account_number",
            "ifsc_code",
            "bank_name",
            "status",
            "is_phone_verified",
            "is_email_verified",
            "is_document_verified",
            "created_at",
            "updated_at",
            "logo",
            "banner_image",
            "brand_color",
            "promotional_codes",
            "shipping_methods",
            "shipping_days",
            "free_shipping_threshold",
        ]


class ShippingLocationSerializer(serializers.ModelSerializer):
    """Serializer for ShippingLocation model with enhanced validation"""

    # Add custom validators for pincode and phone number
    pincode = serializers.CharField(
        validators=[
            RegexValidator(regex=r"^\d{6}$", message="Pincode must be 6 digits")
        ]
    )

    phone_number = serializers.CharField(
        validators=[
            RegexValidator(
                regex=r"^\+?91?\d{10}$",
                message="Phone number must be 10 digits with optional +91",
            )
        ]
    )

    # Add a seller field for read-only display
    seller_name = serializers.CharField(source="seller.business_name", read_only=True)

    class Meta:
        model = ShippingLocation
        fields = [
            "id",
            "seller_name",  # Added instead of seller_email
            "address",
            "city",
            "state",
            "pincode",
            "phone_number",
        ]
        # No need for extra_kwargs since seller_name is already read_only

    def validate(self, data):
        """
        Additional cross-field validation
        """
        # Example validation: Check if the city and state combination is valid
        city = data.get("city")
        state = data.get("state")

        # Add any specific validation logic here
        # For example, you could check if the pincode matches the city/state

        return data


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model"""

    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "sku", "quantity", "price"]


class OrderSerializer(serializers.ModelSerializer):
    """Enhanced Order Serializer with nested item creation"""

    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "seller",
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",
            "customer_city",
            "customer_state",
            "customer_pincode",
            "total_price",
            "length",
            "breadth",
            "height",
            "weight",
            "payment_method",
            "order_status",
            "tracking_number",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = [
            "id",
            "order_status",
            "tracking_number",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """
        Comprehensive order validation
        """
        # Validate total price
        if data.get("total_price", 0) <= 0:
            raise serializers.ValidationError("Total price must be positive")

        # Validate customer contact information
        if not data.get("customer_email"):
            raise serializers.ValidationError("Customer email is required")

        # Validate items
        items_data = data.get("items", [])
        if not items_data:
            raise serializers.ValidationError("At least one order item is required")

        return data

    def create(self, validated_data):
        """
        Create order with nested items
        """
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        return order

    def update(self, instance, validated_data):
        """
        Update order with nested items
        """
        # Remove items from validated data
        items_data = validated_data.pop("items", None)

        # Update order instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update items if provided
        if items_data:
            # Remove existing items
            instance.items.all().delete()

            # Create new items
            for item_data in items_data:
                OrderItem.objects.create(order=instance, **item_data)

        return instance


from rest_framework import serializers
from django.core.validators import RegexValidator


class PanCardUploadSerializer(serializers.Serializer):
    """
    Serializer for PAN card document upload
    """

    pan_document = serializers.FileField(
        required=True,
        error_messages={"required": "Please upload your PAN card document"},
    )

    pan_number = serializers.CharField(
        required=True,
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
                message="Invalid PAN number format. It should be in the format AAAAA0000A",
            )
        ],
        error_messages={
            "required": "PAN number is required",
            "max_length": "PAN number must be 10 characters",
        },
    )

    def validate_pan_document(self, value):
        """Validate the PAN card document"""
        # Make sure file size is less than 5MB
        if value.size > 5 * 1024 * 1024:  # 5MB
            raise serializers.ValidationError("File size must be less than 5MB")

        # Check file extension
        import os

        ext = os.path.splitext(value.name)[1].lower()
        allowed_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )

        return value
