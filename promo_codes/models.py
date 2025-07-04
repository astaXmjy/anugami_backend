from django.db import models
from django.utils.timezone import now


class PromoCode(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("expired", "Expired"),
    ]

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]

    promo_code = models.CharField(max_length=50, unique=True)
    message = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    number_of_users = models.PositiveIntegerField()
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    repeat_usage = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    main_image = models.ImageField(upload_to="promo_images/", null=True, blank=True)
    list_promo_code = models.BooleanField(default=True)
    used_count = models.PositiveIntegerField(default=0)

    def is_valid(self):
        """Check if the promo code is active and within the valid date range"""
        if self.status != "active":
            return False
        if not (self.start_date <= now().date() <= self.end_date):
            return False
        if self.used_count >= self.number_of_users:
            return False
        return True

    def apply_discount(self, order_amount):
        """Apply the discount and return the new order amount"""
        if self.is_valid() and order_amount >= self.minimum_order_amount:
            if self.discount_type == "percentage":
                discount_amount = (self.discount / 100) * order_amount
            else:
                discount_amount = self.discount

            discount_amount = min(discount_amount, self.max_discount_amount)
            return order_amount - discount_amount, discount_amount
        return order_amount, 0

    def __str__(self):
        return f"{self.promo_code} ({self.status})"
