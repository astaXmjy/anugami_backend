from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Count
from .models import ShippingPolicy
from .serializers import ShippingPolicySerializer
from .services import ShippingPolicyService
import logging


logger = logging.getLogger(__name__)


class IsSellerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow sellers to manage their own shipping policies
    """

    def has_permission(self, request, view):
        is_staff = request.user.is_staff
        has_seller = hasattr(request.user, "seller")
        seller_value = getattr(request.user, "seller", None)

        logger.debug(
            f"User {request.user.username}: is_staff={is_staff}, has_seller={has_seller}, seller_value={seller_value}"
        )

        # Admin can do anything
        if is_staff:
            return True

        # Check if user is a seller
        return has_seller and seller_value is not None

    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.is_staff:
            return True

        # Check if user is the seller
        return hasattr(request.user, "seller") and obj.seller == request.user.seller


class PublicShippingPolicyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for public access to shipping policies - read only
    """

    serializer_class = ShippingPolicySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Return active policies for public access"""
        return ShippingPolicy.objects.filter(is_active=True)


class ShippingPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for shipping policies - full CRUD for sellers and admins
    """

    serializer_class = ShippingPolicySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter policies based on user"""
        user = self.request.user

        # Admin can see all policies
        if user.is_staff:
            return ShippingPolicy.objects.all()

        # Get the seller profile for the authenticated user
        from sellers.models import Seller

        try:
            # Try different ways to get the seller associated with this user
            # Option 1: Direct seller attribute
            if hasattr(user, "seller"):
                seller = user.seller
            # Option 2: Through seller_profile relationship
            elif hasattr(user, "seller_profile"):
                seller = user.seller_profile
            # Option 3: Lookup by email
            else:
                seller = Seller.objects.filter(email=user.email).first()

            if seller:
                return ShippingPolicy.objects.filter(seller=seller)
        except Exception as e:
            logger.error(f"Error getting seller for user {user.id}: {str(e)}")

        # Return empty queryset if no seller found
        return ShippingPolicy.objects.none()

    def perform_create(self, serializer):
        """Set seller and created_by when creating policy"""
        user = self.request.user

        # Find the seller associated with this user
        from sellers.models import Seller

        seller = None

        try:
            # Try different ways to get the seller
            # Option 1: Direct seller attribute
            if hasattr(user, "seller"):
                seller = user.seller
            # Option 2: Through seller_profile relationship
            elif hasattr(user, "seller_profile"):
                seller = user.seller_profile
            # Option 3: Lookup by email
            else:
                seller = Seller.objects.filter(email=user.email).first()

            if not seller and not user.is_staff:
                # If no seller found and not admin, raise error
                from rest_framework.exceptions import ValidationError

                raise ValidationError(
                    {"seller": "No seller profile found for this user."}
                )

            # If admin, check if seller ID is provided
            if not seller and user.is_staff:
                seller_id = self.request.data.get("seller")
                if not seller_id:
                    from rest_framework.exceptions import ValidationError

                    raise ValidationError(
                        {
                            "seller": "Seller ID is required when creating a policy as admin."
                        }
                    )

                seller = get_object_or_404(Seller, id=seller_id)

            # Check for unique title
            title = self.request.data.get("title")
            if (
                title
                and ShippingPolicy.objects.filter(seller=seller, title=title).exists()
            ):
                from rest_framework.exceptions import ValidationError

                raise ValidationError(
                    {
                        "title": f"A policy with title '{title}' already exists for this seller."
                    }
                )

            # Save with proper attributes
            serializer.save(seller=seller, created_by=user, updated_by=user)

        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            logger.error(f"Error creating shipping policy: {str(e)}")
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {"error": f"Failed to create shipping policy: {str(e)}"}
            )

    def perform_update(self, serializer):
        """Set updated_by when updating policy"""
        user = self.request.user
        instance = self.get_object()

        # Check for title uniqueness if it's being changed
        new_title = self.request.data.get("title")
        if new_title and new_title != instance.title:
            # Check if another policy with this title exists for this seller
            if (
                ShippingPolicy.objects.filter(seller=instance.seller, title=new_title)
                .exclude(pk=instance.pk)
                .exists()
            ):
                from rest_framework.exceptions import ValidationError

                raise ValidationError(
                    {
                        "title": f"A policy with title '{new_title}' already exists for this seller."
                    }
                )

        # Save with updated_by attribute
        serializer.save(updated_by=user)

    @action(detail=False, methods=["get"])
    def default(self, request):
        """Get default shipping policy for the seller"""
        # Find the seller associated with this user
        from sellers.models import Seller

        seller = None

        try:
            # Try different ways to get the seller
            # Option 1: Direct seller attribute
            if hasattr(request.user, "seller"):
                seller = request.user.seller
            # Option 2: Through seller_profile relationship
            elif hasattr(request.user, "seller_profile"):
                seller = request.user.seller_profile
            # Option 3: Lookup by email
            else:
                seller = Seller.objects.filter(email=request.user.email).first()

            if not seller:
                return Response(
                    {"error": "No seller profile found for this user"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            policy = ShippingPolicy.objects.get(seller=seller, is_default=True)
            serializer = self.get_serializer(policy)
            return Response(serializer.data)
        except ShippingPolicy.DoesNotExist:
            return Response(
                {"error": "No default shipping policy found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error getting default policy: {str(e)}")
            return Response(
                {"error": f"Failed to get default policy: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        """Set a policy as default"""
        policy = self.get_object()

        try:
            # Set this policy as default (will unset others)
            policy.is_default = True
            policy.save()

            return Response({"message": "Default policy updated"})
        except Exception as e:
            logger.error(f"Error setting default policy: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get statistics about shipping policies"""
        # Only admins can access statistics
        if not request.user.is_staff:
            return Response(
                {"error": "Only administrators can access statistics"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get statistics
        try:
            total_policies = ShippingPolicy.objects.count()
            active_policies = ShippingPolicy.objects.filter(is_active=True).count()
            default_policies = ShippingPolicy.objects.filter(is_default=True).count()
            policies_by_seller = (
                ShippingPolicy.objects.values("seller")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            # Get seller names
            from sellers.models import Seller

            seller_ids = [item["seller"] for item in policies_by_seller]
            # Use business_name instead of name
            sellers = {
                s.id: getattr(s, "business_name", str(s))
                for s in Seller.objects.filter(id__in=seller_ids)
            }

            for policy in policies_by_seller:
                policy["seller_name"] = sellers.get(policy["seller"], "Unknown")

            return Response(
                {
                    "total_policies": total_policies,
                    "active_policies": active_policies,
                    "default_policies": default_policies,
                    "policies_by_seller": policies_by_seller,
                }
            )
        except Exception as e:
            logger.error(f"Error getting shipping policy statistics: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve statistics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Legacy function-based views for compatibility
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_shipping_policy(request):
    """Create a shipping policy for a seller"""
    user = request.user
    from sellers.models import Seller

    seller = None

    # Try different ways to get the seller
    if hasattr(user, "seller"):
        seller = user.seller
    elif hasattr(user, "seller_profile"):
        seller = user.seller_profile
    else:
        # Try looking up by email
        seller = Seller.objects.filter(email=user.email).first()

    if not seller and not user.is_staff:
        return Response(
            {"error": "No seller profile found for this user"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # For admin users, get seller from request data
    if not seller and user.is_staff:
        seller_id = request.data.get("seller")
        if not seller_id:
            return Response(
                {"error": "Seller ID is required when creating as admin"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        seller = get_object_or_404(Seller, id=seller_id)

    policy_data = request.data

    # Validate required fields
    required_fields = [
        "title",
        "description",
        "return_policy",
        "delivery_time",
        "shipping_cost",
    ]
    for field in required_fields:
        if field not in policy_data:
            return Response(
                {"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST
            )

    try:
        policy = ShippingPolicyService.create_shipping_policy(
            seller=seller, policy_data=policy_data, user=user
        )

        serializer = ShippingPolicySerializer(policy)
        return Response(
            {"message": "Shipping policy created", "policy": serializer.data},
            status=status.HTTP_201_CREATED,
        )
    except Exception as e:
        logger.error(f"Error in create_shipping_policy: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def list_shipping_policies(request):
    """Retrieve shipping policies"""
    user = request.user

    # Different behavior based on user type
    if not user.is_authenticated:
        # Unauthenticated users see active policies
        policies = ShippingPolicy.objects.filter(is_active=True)
    elif user.is_staff:
        # Admin users see all policies
        policies = ShippingPolicy.objects.all()
    elif hasattr(user, "seller"):
        # Sellers see their own policies
        policies = ShippingPolicy.objects.filter(seller=user.seller)
    else:
        # Try to find seller by email
        from sellers.models import Seller

        seller = Seller.objects.filter(email=user.email).first()
        if seller:
            policies = ShippingPolicy.objects.filter(seller=seller)
        else:
            # Regular authenticated users see active policies
            policies = ShippingPolicy.objects.filter(is_active=True)

    serializer = ShippingPolicySerializer(policies, many=True)
    return Response({"shipping_policies": serializer.data}, status=status.HTTP_200_OK)


@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def update_shipping_policy(request, policy_id):
    """Update a shipping policy"""
    user = request.user

    # Try different ways to get the seller
    from sellers.models import Seller

    seller = None

    if hasattr(user, "seller"):
        seller = user.seller
    elif hasattr(user, "seller_profile"):
        seller = user.seller_profile
    else:
        # Try looking up by email
        seller = Seller.objects.filter(email=user.email).first()

    if not seller and not user.is_staff:
        return Response(
            {"error": "You don't have permission to update policies"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Get the policy
    policy = get_object_or_404(ShippingPolicy, id=policy_id)

    # Check permissions
    if not user.is_staff and (not seller or policy.seller != seller):
        return Response(
            {"error": "Policy does not belong to this seller"},
            status=status.HTTP_403_FORBIDDEN,
        )

    update_data = request.data

    try:
        updated_policy = ShippingPolicyService.update_shipping_policy(
            policy_id=policy_id, update_data=update_data, user=user
        )

        serializer = ShippingPolicySerializer(updated_policy)
        return Response(
            {"message": "Shipping policy updated", "policy": serializer.data},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.error(f"Error in update_shipping_policy: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def delete_shipping_policy(request, policy_id):
    """Delete a shipping policy"""
    user = request.user

    # Try different ways to get the seller
    from sellers.models import Seller

    seller = None

    if hasattr(user, "seller"):
        seller = user.seller
    elif hasattr(user, "seller_profile"):
        seller = user.seller_profile
    else:
        # Try looking up by email
        seller = Seller.objects.filter(email=user.email).first()

    if not seller and not user.is_staff:
        return Response(
            {"error": "You don't have permission to delete policies"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Get the policy
    policy = get_object_or_404(ShippingPolicy, id=policy_id)

    # Check permissions
    if not user.is_staff and (not seller or policy.seller != seller):
        return Response(
            {"error": "Policy does not belong to this seller"},
            status=status.HTTP_403_FORBIDDEN,
        )

    success = ShippingPolicyService.delete_shipping_policy(policy_id)

    if success:
        return Response(
            {"message": "Shipping policy deleted"}, status=status.HTTP_204_NO_CONTENT
        )
    else:
        return Response(
            {"error": "Failed to delete shipping policy"},
            status=status.HTTP_400_BAD_REQUEST,
        )
