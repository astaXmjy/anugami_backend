from django.apps import AppConfig


class ShippingPoliciesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shipping_policies"
    verbose_name = "Shipping Policy Management"

    def ready(self):
        # Import signals
        import shipping_policies.signals
