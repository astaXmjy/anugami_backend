from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now

class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    SUCCESS = "SUCCESS", _("Success")
    FAILURE = "FAILURE", _("Failure")
    REFUNDED = "REFUNDED", _("Refunded")

class Payment(models.Model):
    order_id = models.CharField(max_length=50, unique=True)
    transaction_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    phonepe_transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    shipping_charge = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    markup_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    phonepe_charge = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_total(self):
        """Calculate total amount including GST, shipping, markup, and PhonePe charge."""
        self.total_amount = self.amount + self.gst + self.shipping_charge + self.markup_fee + self.phonepe_charge
        return self.total_amount

    def __str__(self):
        return f"Payment {self.order_id} - {self.status}"
