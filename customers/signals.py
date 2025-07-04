# customers/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer

@receiver(post_save, sender=Customer)
def customer_created(sender, instance, created, **kwargs):
    """Signal to perform actions when a new customer is created"""
    if created:
        print(f"New customer created: {instance.email}")
