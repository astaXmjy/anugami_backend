from django.db import models
from django.conf import settings
import uuid
from decimal import Decimal
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
    # ========== EXISTING FIELDS (keeping all as-is) ==========
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

    # ========== NEW FIELDS FOR COMMISSION & PRICING BREAKDOWN ==========
    
    # Additional pricing fields
    delivery_charges = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Delivery charges for information collection"
    )
    listing_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Listing price from your table"
    )
    consumer_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Consumer price from your table"
    )
    
    # Commission calculations
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.00,
        help_text="Commission rate as percentage (gets from seller)"
    )
    commission_for_each_seller = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Commission amount for each seller"
    )
    commission_for_each_seller_gst = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="GST on commission amount"
    )
    
    # GST calculations (enhanced from existing tax fields)
    gst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=18.00,
        help_text="GST rate as percentage"
    )
    gst_amount_inclusive = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="GST amount inclusive in the sale"
    )
    
    # Seller financial breakdown
    amount_seller_receives = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Amount seller receives after commission and GST"
    )
    amount_receives_after_paying = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Amount seller receives after paying all charges"
    )
    claimable_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Claimable amount by seller"
    )
    gst_amount_seller = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="GST amount for seller"
    )
    
    # Profit calculations
    profit_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Profit amount after paying seller"
    )
    
    # Shipping cost (fixed as requested)
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=150.00,
        help_text="Fixed shipping cost of 150 Rs"
    )
    
    # COD charges if applicable
    cod_charges = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="COD charges if payment method is COD"
    )
    
    # Timestamps for the new fields
    commission_calculated_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Auto-calculate all the derived fields before saving
        self.calculate_commission_and_amounts()
        super().save(*args, **kwargs)
    
    def calculate_commission_and_amounts(self):
        """
        Calculate all commission and financial amounts based on the pricing structure
        from your table requirements
        """
        if not self.order or not self.order.seller:
            return
        
        # Get seller's commission rate
        self.commission_rate = self.order.seller.commission_rate
        
        # Use sale_price as base price (equivalent to "Sale price" in your table)
        base_price = self.sale_price or self.price
        total_item_amount = base_price * self.quantity
        
        # Calculate commission for each seller (25% of base price as per your table example)
        # Adjusting based on seller's actual commission rate
        self.commission_for_each_seller = (total_item_amount * self.commission_rate / 100)
        
        # Calculate GST on commission (18% GST on commission)
        commission_gst_rate = Decimal('18.00')  # 18% GST on commission
        self.commission_for_each_seller_gst = (self.commission_for_each_seller * commission_gst_rate / 100)
        
        # Calculate GST amount inclusive (18% of base amount)
        if not self.gst_rate:
            self.gst_rate = Decimal('18.00')  # Default 18% GST
        
        self.gst_amount_inclusive = (total_item_amount * self.gst_rate / 100)
        
        # Update the existing tax_amount field to match gst_amount_inclusive
        self.tax_amount = self.gst_amount_inclusive
        
        # Calculate amount seller receives (base amount - commission - GST)
        self.amount_seller_receives = (
            total_item_amount - 
            self.commission_for_each_seller - 
            self.gst_amount_inclusive
        )
        
        # Calculate amount after paying (seller receives - shipping cost)
        self.amount_receives_after_paying = self.amount_seller_receives - self.shipping_cost
        
        # Set claimable amount (same as amount after paying in most cases)
        self.claimable_amount = self.amount_receives_after_paying
        
        # GST amount for seller (could be different calculation if needed)
        self.gst_amount_seller = self.gst_amount_inclusive
        
        # Calculate profit amount (consumer_price - sale_price) * quantity
        if self.consumer_price and self.sale_price:
            self.profit_amount = (self.consumer_price - self.sale_price) * self.quantity
        else:
            # Fallback: assume some profit margin
            self.profit_amount = total_item_amount * Decimal('0.10')  # 10% profit margin
        
        # Update final_price to include all costs
        self.final_price = total_item_amount + self.shipping_cost + self.cod_charges
        
        # Set timestamp
        from django.utils import timezone
        self.commission_calculated_at = timezone.now()
    
    def get_financial_breakdown(self):
        """
        Return a dictionary with complete financial breakdown matching your table structure
        """
        return {
            # Basic product info
            'product_name': self.name,
            'sku': self.sku,
            'quantity': self.quantity,
            
            # Pricing breakdown
            'sale_price': self.sale_price or self.price,
            'delivery_charges': self.delivery_charges,
            'listing_price': self.listing_price,
            'consumer_price': self.consumer_price,
            
            # Commission breakdown
            'commission_rate': f"{self.commission_rate}%",
            'commission_for_each_seller': self.commission_for_each_seller,
            'commission_for_each_seller_gst': self.commission_for_each_seller_gst,
            
            # GST breakdown
            'gst_rate': f"{self.gst_rate}%",
            'gst_amount_inclusive': self.gst_amount_inclusive,
            'gst_amount_seller': self.gst_amount_seller,
            
            # Seller financial info
            'amount_seller_receives': self.amount_seller_receives,
            'amount_receives_after_paying': self.amount_receives_after_paying,
            'claimable_amount': self.claimable_amount,
            
            # Additional costs
            'shipping_cost': self.shipping_cost,
            'cod_charges': self.cod_charges,
            
            # Profit info
            'profit_amount': self.profit_amount,
            'final_price': self.final_price,
        }
    
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


# In orders/models.py - Update the ShippingDetails model

class ShippingDetails(models.Model):
    """Enhanced ShippingDetails model with Shipmojo integration fields"""

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="shipping"
    )
    provider = models.CharField(max_length=50, default="shipmojo")

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

    # Shipmojo specific fields (replacing Shiprocket fields)
    shipmojo_order_id = models.CharField(max_length=50, blank=True, null=True)
    shipmojo_reference_id = models.CharField(max_length=50, blank=True, null=True)
    courier_company_id = models.CharField(max_length=20, blank=True, null=True)
    courier_company_service = models.CharField(max_length=100, blank=True, null=True)
    warehouse_id = models.CharField(max_length=50, blank=True, null=True)
    lr_number = models.CharField(max_length=100, blank=True, null=True)
    label_url = models.URLField(blank=True, null=True)
    label_data = models.TextField(blank=True, null=True)  # For base64 label data
    pickup_token_number = models.CharField(max_length=100, blank=True, null=True)
    status_code = models.CharField(max_length=20, blank=True, null=True)
    shipmojo_response = models.JSONField(default=dict, blank=True)
    
    # Additional fields for multi-seller support
    seller = models.ForeignKey(
        'sellers.Seller', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Seller associated with this shipment"
    )
    
    # Courier assignment tracking
    courier_assigned = models.BooleanField(default=False)
    courier_assigned_at = models.DateTimeField(null=True, blank=True)
    pickup_scheduled_manually = models.BooleanField(default=False)
    
    # Return order fields
    is_return_order = models.BooleanField(default=False)
    return_reason_id = models.IntegerField(null=True, blank=True)
    return_reason_comment = models.TextField(blank=True, null=True)
    customer_request = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Shipping for {self.order.order_number}"

    class Meta:
        verbose_name = "Shipping Details"
        verbose_name_plural = "Shipping Details"


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
