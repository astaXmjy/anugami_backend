import logging
from django.db import transaction
from .models import ShippingPolicy, ShippingZone
from products.models import Product

logger = logging.getLogger(__name__)


class ShippingPolicyService:
    """Service class for managing shipping policies"""

    @staticmethod
    def create_shipping_policy(seller, policy_data, user=None):
        """
        Create a new shipping policy for a seller

        Args:
            seller: Seller model instance
            policy_data: Dictionary containing policy data
            user: User creating the policy (optional)

        Returns:
            ShippingPolicy: The created policy instance
        """
        try:
            zones_data = (
                policy_data.pop("zones", []) if isinstance(policy_data, dict) else []
            )

            with transaction.atomic():
                # Create the policy
                policy = ShippingPolicy.objects.create(
                    seller=seller, created_by=user, updated_by=user, **policy_data
                )

                # Create zones if provided
                for zone_data in zones_data:
                    ShippingZone.objects.create(policy=policy, **zone_data)

                # Use business_name instead of name
                seller_name = getattr(seller, "business_name", str(seller))
                logger.info(
                    f"Created shipping policy: {policy.title} for seller: {seller_name}"
                )
                return policy

        except Exception as e:
            logger.error(f"Error creating shipping policy: {str(e)}")
            raise

    @staticmethod
    def update_shipping_policy(policy_id, update_data, user=None):
        """
        Update an existing shipping policy

        Args:
            policy_id: ID of the policy to update
            update_data: Dictionary containing updated data
            user: User updating the policy (optional)

        Returns:
            ShippingPolicy: The updated policy instance
        """
        try:
            policy = ShippingPolicy.objects.get(id=policy_id)
            zones_data = update_data.pop("zones", None)

            with transaction.atomic():
                # Update policy fields
                for key, value in update_data.items():
                    setattr(policy, key, value)

                if user:
                    policy.updated_by = user

                policy.save()

                # Update zones if provided
                if zones_data is not None:
                    # Delete existing zones
                    policy.zones.all().delete()

                    # Create new zones
                    for zone_data in zones_data:
                        ShippingZone.objects.create(policy=policy, **zone_data)

                # Update cached policy data in products
                ShippingPolicyService.update_product_policies(policy)

                logger.info(f"Updated shipping policy: {policy.title}")
                return policy

        except ShippingPolicy.DoesNotExist:
            logger.error(f"Shipping policy not found: {policy_id}")
            raise
        except Exception as e:
            logger.error(f"Error updating shipping policy: {str(e)}")
            raise

    @staticmethod
    def get_policy_by_id(policy_id):
        """
        Get a shipping policy by ID

        Args:
            policy_id: ID of the policy

        Returns:
            ShippingPolicy or None: The policy if found, None otherwise
        """
        try:
            return ShippingPolicy.objects.get(id=policy_id)
        except ShippingPolicy.DoesNotExist:
            return None

    @staticmethod
    def get_seller_policies(seller):
        """
        Get all shipping policies for a seller

        Args:
            seller: Seller model instance

        Returns:
            QuerySet: ShippingPolicy queryset
        """
        return ShippingPolicy.objects.filter(seller=seller)

    @staticmethod
    def delete_shipping_policy(policy_id):
        """
        Delete a shipping policy

        Args:
            policy_id: ID of the policy to delete

        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            policy = ShippingPolicy.objects.get(id=policy_id)

            with transaction.atomic():
                # Clear policy references from products
                products = Product.objects.filter(shipping_policy_id=policy_id)
                for product in products:
                    product.shipping_policy_id = None
                    product.shipping_policy_data = {}
                    product.save()

                # Delete the policy (will cascade delete zones)
                policy.delete()

                logger.info(f"Deleted shipping policy: {policy.title}")
                return True

        except ShippingPolicy.DoesNotExist:
            logger.error(f"Shipping policy not found: {policy_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting shipping policy: {str(e)}")
            return False

    @staticmethod
    def update_product_policies(policy):
        """
        Update cached policy data in all products using this policy

        Args:
            policy: ShippingPolicy instance
        """
        try:
            # Convert policy to dict representation
            from .serializers import ShippingPolicySerializer

            policy_data = ShippingPolicySerializer(policy).data

            # Update products using this policy
            products = Product.objects.filter(shipping_policy_id=policy.id)
            for product in products:
                product.shipping_policy_data = policy_data
                product.save()

            logger.info(
                f"Updated {products.count()} products with policy: {policy.title}"
            )

        except Exception as e:
            logger.error(f"Error updating product policies: {str(e)}")
            raise
