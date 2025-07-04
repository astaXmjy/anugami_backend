# customers/models.py
from pyexpat import model
from django.db import models
from django.conf import settings
import uuid


class Customer(models.Model):
    """Main customer model"""

    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer"
    )
    full_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        null=True,
        blank=True,
    )
    profile_picture = models.URLField(null=True, blank=True)
    firebase_uid = models.CharField(max_length=255, null=True, blank=True, unique=True)
    is_phone_verified = models.BooleanField(default=False)
    status = models.CharField(
        max_length=10,
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("suspended", "Suspended"),
        ],
        default="active",
    )
    last_active = models.DateTimeField(null=True, blank=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    reward_points = models.IntegerField(default=0)
    total_orders = models.IntegerField(default=0)
    total_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers_customer"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"

    @property
    def email(self):
        return self.user.email if self.user else None

    @property
    def phone(self):
        return self.user.phone_number if self.user else None


class Address(models.Model):
    """Customer Address Model"""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="addresses"
    )
    address_type = models.CharField(
        max_length=10, choices=[("home", "Home"), ("work", "Work"), ("other", "Other")]
    )
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    street = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=50, default="India")
    pincode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "customers_address"
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.full_name} - {self.city}"


class CartItem(models.Model):
    """Cart Items Model"""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="cart_items"
    )
    product_id = models.CharField(max_length=255)
    variant_id = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers_cartitem"
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"

    def __str__(self):
        return f"{self.product_id} - {self.quantity}"


class WishlistItem(models.Model):
    """Wishlist Items Model"""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="wishlist_items"
    )
    product_id = models.CharField(max_length=255)
    variant_id = models.CharField(max_length=255, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customers_wishlistitem"
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"

    def __str__(self):
        return f"{self.product_id} (Wishlist)"


class CustomerPreferences(models.Model):
    """Customer Preferences Model"""

    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="preferences"
    )
    currency = models.CharField(max_length=5, default="INR")
    language = models.CharField(max_length=5, default="en")
    notification_preferences = models.JSONField(
        default=dict
    )  # {'email': True, 'sms': True, 'push': False}
    marketing_preferences = models.JSONField(
        default=dict
    )  # {'email_marketing': True, 'sms_marketing': False}

    class Meta:
        db_table = "customers_preferences"
        verbose_name = "Customer Preference"
        verbose_name_plural = "Customer Preferences"

    def __str__(self):
        return f"Preferences for {self.customer.full_name}"


class CustomerActivity(models.Model):
    """Tracks customer interactions with products and categories"""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="activities"
    )
    product_id = models.CharField(max_length=255, null=True, blank=True)
    interaction_type = models.CharField(
        max_length=50,
        choices=[
            ("view", "View"),
            ("cart", "Cart"),
            ("wishlist", "Wishlist"),
            ("purchase", "Purchase"),
        ],
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    category_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "customers_activity"
        verbose_name = "Customer Activity"
        verbose_name_plural = "Customer Activities"

    def __str__(self):
        return f"{self.customer.full_name} - {self.interaction_type}"


class CustomerTransaction(models.Model):
    """Tracks customer transactions (wallet, payments, refunds)"""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=[("credit", "Credit"), ("debit", "Debit"), ("refund", "Refund")],
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customers_transaction"
        verbose_name = "Customer Transaction"
        verbose_name_plural = "Customer Transactions"

    def __str__(self):
        return f"{self.customer.full_name} - {self.transaction_type} - {self.amount}"


class CustomerOrderStats(models.Model):
    """Stores customer order statistics"""

    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="order_stats"
    )
    total_orders = models.PositiveIntegerField(default=0)
    total_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    last_order_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "customers_orderstats"
        verbose_name = "Customer Order Stats"
        verbose_name_plural = "Customer Order Stats"

    def __str__(self):
        return f"{self.customer.full_name} - {self.total_orders} Orders"

class ContactUs(models.Model):
    customer=models.ForeignKey(Customer,on_delete=models.CASCADE,related_name="contactus")
    name=models.CharField(max_length=100)
    email=models.EmailField()
    subject=models.CharField(max_length=100)
    phone=models.CharField(max_length=15)
    message=models.TextField()
