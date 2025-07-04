from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ShippingPolicy, ShippingZone
from products.models import Product
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ShippingPolicy)
def handle_shipping_policy_save(sender, instance, created, **kwargs):
    """
    Update product data when shipping policy is updated
    """
    try:
        # Convert policy to dict representation for caching in products
        from .serializers import ShippingPolicySerializer

        policy_data = ShippingPolicySerializer(instance).data

        # Update all products using this policy
        products = Product.objects.filter(shipping_policy_id=instance.id)
        for product in products:
            product.shipping_policy_data = policy_data
            product.save(update_fields=["shipping_policy_data"])

        logger.info(
            f"Updated {products.count()} products with policy: {instance.title}"
        )

    except Exception as e:
        logger.error(f"Error in shipping policy post-save signal: {str(e)}")


@receiver(post_save, sender=ShippingZone)
def handle_shipping_zone_save(sender, instance, created, **kwargs):
    """
    Update policy when zone is updated to trigger product updates
    """
    try:
        policy = instance.policy
        policy.save()  # This will trigger the policy post_save signal

    except Exception as e:
        logger.error(f"Error in shipping zone post-save signal: {str(e)}")


@receiver(post_delete, sender=ShippingPolicy)
def handle_shipping_policy_delete(sender, instance, **kwargs):
    """
    Clear shipping policy reference from products when policy is deleted
    """
    try:
        # Update all products using this policy
        products = Product.objects.filter(shipping_policy_id=instance.id)
        for product in products:
            product.shipping_policy_id = None
            product.shipping_policy_data = {}
            product.save(update_fields=["shipping_policy_id", "shipping_policy_data"])

        logger.info(f"Cleared policy reference from {products.count()} products")

    except Exception as e:
        logger.error(f"Error in shipping policy post-delete signal: {str(e)}")
