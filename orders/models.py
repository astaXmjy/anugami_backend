from django.db import models
from django.conf import settings
import uuid
from customers.models import Customer
from sellers.models import Seller


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("returned", "Returned"),
    ]

    id = models.AutoField(primary_key=True)
    order_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="customer_orders"
    )
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="seller_orders"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Only generate order number for new orders (not updates)
        if not self.order_number:
            # Get the highest order number
            latest_order = Order.objects.all().order_by("-id").first()

            # Start with 100 if no orders exist
            if not latest_order:
                order_num = 100
            else:
                # Try to extract the number from the latest order number
                try:
                    if latest_order.order_number.startswith("ANU-"):
                        latest_num = int(latest_order.order_number[4:])
                        order_num = latest_num + 1
                    else:
                        # If the format doesn't match, default to 100
                        order_num = 100
                except (ValueError, AttributeError):
                    # If there's an error parsing, default to 100
                    order_num = 100

            # Format with ANU prefix
            self.order_number = f"ANU-{order_num}"

        super().save(*args, **kwargs)

    def _str_(self):
        return f"Order #{self.order_number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product_id = models.CharField(max_length=100)
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    quantity = models.PositiveIntegerField()
    tax_rate = models.FloatField(null=True, blank=True)
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    return_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, default="pending")
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} x {self.quantity}"


class OrderAddress(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    address_type = models.CharField(
        max_length=20, choices=[("shipping", "Shipping"), ("billing", "Billing")]
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    street = models.CharField(max_length=255)
    area = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="India")
    pincode = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.full_name} - {self.address_type}"


class ShippingDetails(models.Model):
    """Enhanced ShippingDetails model with Shiprocket integration fields"""

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="shipping"
    )
    provider = models.CharField(max_length=50, default="shiprocket")

    # Basic shipping fields
    tracking_id = models.CharField(max_length=100, blank=True)
    awb_number = models.CharField(max_length=100, blank=True)
    tracking_url = models.URLField(blank=True)
    courier_name = models.CharField(max_length=100, blank=True)
    speed = models.CharField(
        max_length=20, choices=[("standard", "Standard"), ("express", "Express")]
    )
    weight = models.FloatField()
    length = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()
    pickup_location = models.CharField(max_length=255)
    pickup_scheduled = models.DateTimeField(null=True, blank=True)
    expected_delivery = models.DateTimeField(null=True, blank=True)
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(max_length=50, blank=True)
    status_updates = models.JSONField(default=list, blank=True)

    # Shiprocket specific fields
    shiprocket_order_id = models.CharField(max_length=50, blank=True, null=True)
    shipment_id = models.CharField(max_length=50, blank=True, null=True)
    courier_company_id = models.CharField(max_length=20, blank=True, null=True)
    pickup_token_number = models.CharField(max_length=100, blank=True, null=True)
    label_url = models.URLField(blank=True, null=True)
    manifest_url = models.URLField(blank=True, null=True)
    status_code = models.CharField(max_length=20, blank=True, null=True)
    shiprocket_response = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Shipping for {self.order.order_number}"


class ShipmentStatusUpdate(models.Model):
    """Model to track shipping status history"""

    shipping = models.ForeignKey(
        ShippingDetails, on_delete=models.CASCADE, related_name="status_history"
    )
    status = models.CharField(max_length=100)
    status_date = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, null=True)
    activity = models.CharField(max_length=255, blank=True, null=True)
    additional_info = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-status_date"]

    def __str__(self):
        return f"{self.status} - {self.status_date}"


class PaymentDetails(models.Model):
    """Enhanced PaymentDetails model with PhonePe integration fields"""

    PAYMENT_CHOICES = [
        ("COD", "Cash on Delivery"),
        ("PhonePe-UPI", "PhonePe UPI"),
        ("PhonePe-Wallet", "PhonePe Wallet"),
        ("PhonePe-Card", "PhonePe Card"),
    ]
    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refund_initiated", "Refund Initiated"),
        ("refunded", "Refunded"),
    ]

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="payment"
    )
    method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    transaction_id = models.CharField(max_length=200, blank=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS, default="pending"
    )
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    refund_status = models.CharField(max_length=50, blank=True)
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # PhonePe specific fields
    phonepe_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    phonepe_status = models.CharField(
        max_length=50,
        choices=[
            ("PAYMENT_INITIATED", "Payment Initiated"),
            ("PAYMENT_SUCCESS", "Payment Success"),
            ("PAYMENT_PENDING", "Payment Pending"),
            ("PAYMENT_DECLINED", "Payment Declined"),
            ("PAYMENT_ERROR", "Payment Error"),
            ("PAYMENT_CANCELLED", "Payment Cancelled"),
            ("PAYMENT_EXPIRED", "Payment Expired"),
        ],
        blank=True,
        null=True,
    )
    payment_instrument = models.CharField(max_length=50, blank=True, null=True)
    payment_url = models.URLField(max_length=500, blank=True, null=True)
    callback_url = models.URLField(blank=True, null=True)
    redirect_url = models.URLField(blank=True, null=True)
    phonepe_response = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Payment for {self.order.order_number} - {self.payment_status}"


class RefundDetails(models.Model):
    """Model to track refund details"""

    REFUND_STATUS_CHOICES = [
        ("REFUND_INITIATED", "Refund Initiated"),
        ("REFUND_PENDING", "Refund Pending"),
        ("REFUND_SUCCESS", "Refund Success"),
        ("REFUND_FAILED", "Refund Failed"),
    ]

    payment = models.ForeignKey(
        PaymentDetails, on_delete=models.CASCADE, related_name="refunds"
    )
    refund_id = models.CharField(max_length=100)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=50, choices=REFUND_STATUS_CHOICES, default="REFUND_INITIATED"
    )
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_response = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Refund: {self.refund_id}"


# Add this to your models.py file
class InvoiceRequest(models.Model):
    """Model to track customer invoice requests from sellers"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("rejected", "Rejected"),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="invoice_requests"
    )
    requested_by = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="invoice_requests"
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    seller_notes = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    invoice_file = models.FileField(upload_to="invoices/", blank=True, null=True)

    def __str__(self):
        return f"Invoice Request for {self.order.order_number}"
