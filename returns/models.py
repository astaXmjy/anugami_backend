from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now

class ReturnStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")
    REFUNDED = "REFUNDED", _("Refunded")

class ReturnRequest(models.Model):
    order_id = models.CharField(max_length=50)
    product_id = models.CharField(max_length=50)
    customer_email = models.EmailField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=ReturnStatus.choices, default=ReturnStatus.PENDING)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Return for Order {self.order_id} - {self.status}"
