from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Seller(models.Model):
    """
    Seller model for managing vendor profiles with PAN card upload support.
    """

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="seller_profile"
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True)
    business_name = models.CharField(max_length=255)
    business_address = models.TextField(blank=True, null=True)
    gst_number = models.CharField(max_length=15, blank=True, null=True)
    pan_number = models.CharField(max_length=10, blank=True, null=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00,  # Default 15% commission
        help_text="Commission rate as percentage (e.g., 15.00 for 15%)"
    )

    # PAN document URL stored from Firebase
    pan_document_url = models.URLField(blank=True, null=True)

    account_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_document_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Branding fields
    logo = models.ImageField(upload_to="seller_logos/", null=True, blank=True)
    banner_image = models.ImageField(upload_to="seller_banners/", null=True, blank=True)
    brand_color = models.CharField(max_length=7, null=True, blank=True)

    # Promotional codes
    promotional_codes = models.JSONField(default=dict, blank=True, null=True)

    # Shipping settings
    shipping_methods = models.JSONField(default=dict, blank=True, null=True)
    shipping_days = models.JSONField(default=dict, blank=True, null=True)
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.business_name} - {self.status}"

    class Meta:
        db_table = "sellers"
        ordering = ["-created_at"]


class ShippingLocation(models.Model):
    """
    Model to store shipping locations associated with a seller.
    """

    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="shipping_locations"
    )
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6)
    phone_number = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.city}, {self.state} - {self.pincode}"

    class Meta:
        db_table = "shipping_locations"
        ordering = ["-id"]


class Order(models.Model):
    """
    Model for storing seller-specific orders.
    """

    ORDER_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )

    PAYMENT_METHOD_CHOICES = (
        ("Prepaid", "Prepaid"),
        ("COD", "Cash on Delivery"),
    )

    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="orders")
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=15)
    customer_address = models.TextField()
    customer_city = models.CharField(max_length=100)
    customer_state = models.CharField(max_length=100)
    customer_pincode = models.CharField(max_length=6)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    length = models.FloatField()
    breadth = models.FloatField()
    height = models.FloatField()
    weight = models.FloatField()
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    order_status = models.CharField(
        max_length=10, choices=ORDER_STATUS_CHOICES, default="pending"
    )
    tracking_number = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} - {self.order_status}"

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]


class OrderItem(models.Model):
    """
    Model for items in an order.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} (x{self.quantity})"

    class Meta:
        db_table = "order_items"
        ordering = ["-id"]
