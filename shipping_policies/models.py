from django.db import models
from django.utils.translation import gettext_lazy as _
from system_users.models import CustomUser
from sellers.models import Seller


class ShippingPolicy(models.Model):
    """Model for storing seller shipping policies"""

    title = models.CharField(max_length=255)
    description = models.TextField()
    return_policy = models.TextField()
    delivery_time = models.CharField(max_length=100)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2)

    # Seller relationship
    seller = models.ForeignKey(
        Seller, on_delete=models.CASCADE, related_name="shipping_policies"
    )

    # Additional fields
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    max_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Maximum weight in kg"),
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="policies_created",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="policies_updated",
    )

    class Meta:
        verbose_name = _("Shipping Policy")
        verbose_name_plural = _("Shipping Policies")
        unique_together = [["seller", "title"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seller.business_name} - {self.title}"

    def save(self, *args, **kwargs):
        # If this policy is set as default, unset others
        if self.is_default:
            ShippingPolicy.objects.filter(seller=self.seller, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)

        # If no default policy exists, set this one as default
        if (
            not self._state.adding
            and not ShippingPolicy.objects.filter(
                seller=self.seller, is_default=True
            ).exists()
        ):
            self.is_default = True

        super().save(*args, **kwargs)


# Add optional location-based shipping rates
class ShippingZone(models.Model):
    """Model for zone-based shipping rates"""

    policy = models.ForeignKey(
        ShippingPolicy, on_delete=models.CASCADE, related_name="zones"
    )
    name = models.CharField(max_length=100)
    states = models.JSONField(
        help_text=_("List of state/region names covered by this zone"), default=list
    )
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = models.PositiveIntegerField(
        help_text=_("Estimated delivery time in days")
    )

    def __str__(self):
        return f"{self.policy.seller.business_name} - {self.name}"

    class Meta:
        ordering = ["name"]
