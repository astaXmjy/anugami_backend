# orders/permissions.py
from rest_framework import permissions
from system_users.permissions import HasModulePermission


class BaseOrderPermission(permissions.BasePermission):
    """Base class for order permissions with common utilities"""

    def is_customer_order(self, request, obj):
        """Check if order belongs to customer"""
        # Check if user has customer profile and if it matches the order's user
        if hasattr(request.user, "customer") and request.user.customer:
            return obj.user == request.user.customer
        return False

    def is_seller_order(self, request, obj):
        """Check if order belongs to seller"""
        # Check if user has seller profile and if it matches the order's seller
        if hasattr(request.user, "seller_profile") and request.user.seller_profile:
            return obj.seller == request.user.seller_profile
        return False

    def has_staff_permission(self, request, permission_name):
        """Check if user has specific staff permission"""
        # Legacy permission check
        return request.user.is_staff and request.user.has_perm(
            f"orders.{permission_name}"
        )


class OrderModulePermission(HasModulePermission):
    """
    Permission class for orders that:
    1. Gives sellers direct access to their orders, bypassing module permission checks
    2. Gives customers access to their own orders
    3. Falls back to role-based module permissions for admins and staff
    """
    
    def has_permission(self, request, view):
        # Superuser or admin can access everything
        if request.user.is_superuser or (hasattr(request.user, "is_admin") and request.user.is_admin):
            return True
            
        # Sellers get direct access to order endpoints without module permission checks
        if hasattr(request.user, "seller_profile") and request.user.seller_profile:
            # Allow sellers access to standard endpoints and relevant actions
            return True
        
        # Customers can access their own orders
        if hasattr(request.user, "customer") and request.user.customer:
            if view.action in ['list', 'retrieve', 'my_orders']:
                return True
                
        # For all other users, fall back to regular module permission checks
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        # Superuser or admin can access everything
        if request.user.is_superuser or (hasattr(request.user, "is_admin") and request.user.is_admin):
            return True

        # Check module permission for staff users
        if hasattr(request.user, "has_module_permission") and request.user.has_module_permission("orders", "read"):
            return True

        # Sellers can access orders they're associated with
        if hasattr(request.user, "seller_profile") and request.user.seller_profile:
            return obj.seller == request.user.seller_profile

        # Customers can access their own orders
        if hasattr(request.user, "customer") and request.user.customer:
            return obj.user == request.user.customer

        # Default: deny access
        return False


class IsOrderOwner(BaseOrderPermission):
    """Permission to allow only order owner (customer or seller) access"""

    def has_object_permission(self, request, view, obj):
        return self.is_customer_order(request, obj) or self.is_seller_order(
            request, obj
        )


class IsOrderCustomer(BaseOrderPermission):
    """Permission to only allow order customer access"""

    def has_object_permission(self, request, view, obj):
        return self.is_customer_order(request, obj)


class IsOrderSeller(BaseOrderPermission):
    """Permission to only allow order seller access"""

    def has_object_permission(self, request, view, obj):
        return self.is_seller_order(request, obj)


class CanProcessRefunds(BaseOrderPermission):
    """
    Permission for processing refunds
    - System users with refund_orders permission
    - Sellers for their own orders
    - NOT customers
    """

    def has_permission(self, request, view):
        # Check system role-based permission first
        if hasattr(
            request.user, "has_module_permission"
        ) and request.user.has_module_permission("orders", "update"):
            return True

        # Fallback to legacy permission for backward compatibility
        return self.has_staff_permission(request, "refund_orders")

    def has_object_permission(self, request, view, obj):
        # If they have general permission, they can access
        if self.has_permission(request, view):
            return True

        # Sellers can refund their own orders
        if self.is_seller_order(request, obj):
            return True

        # Customers cannot refund (denied)
        return False


class CanManageShipping(BaseOrderPermission):
    """
    Permission for managing shipping
    - System users with ship_orders permission
    - Sellers for their own orders
    - NOT customers
    """

    def has_permission(self, request, view):
        # Check system role-based permission first
        if hasattr(
            request.user, "has_module_permission"
        ) and request.user.has_module_permission("orders", "update"):
            return True

        # Fallback to legacy permission
        return self.has_staff_permission(request, "ship_orders")

    def has_object_permission(self, request, view, obj):
        # If they have general permission, they can access
        if self.has_permission(request, view):
            return True

        # Sellers can manage shipping for their own orders
        if self.is_seller_order(request, obj):
            return True

        # Customers cannot manage shipping (denied)
        return False


class CanCancelOrders(BaseOrderPermission):
    """
    Permission for cancelling orders
    - System users with cancel_orders permission
    - Customers can cancel their own orders
    - Sellers can cancel their own orders
    """

    def has_permission(self, request, view):
        # Check system role-based permission first
        if hasattr(
            request.user, "has_module_permission"
        ) and request.user.has_module_permission("orders", "delete"):
            return True

        # Fallback to legacy permission
        if self.has_staff_permission(request, "cancel_orders"):
            return True

        # Need object-level permission check for customers and sellers
        return True

    def has_object_permission(self, request, view, obj):
        # If they have general permission, they can access
        if hasattr(
            request.user, "has_module_permission"
        ) and request.user.has_module_permission("orders", "delete"):
            return True

        if self.has_staff_permission(request, "cancel_orders"):
            return True

        # Customers can cancel their own orders (with restrictions based on status)
        if self.is_customer_order(request, obj):
            # Only allow cancellation if order status is pending or confirmed
            return obj.status in ["pending", "confirmed"]

        # Sellers can cancel their own orders
        if self.is_seller_order(request, obj):
            return True

        return False


class CanProcessPayments(BaseOrderPermission):
    """
    Permission for processing payments
    - System users with process_orders permission
    - Sellers for their own orders
    - Customers for their own orders (only certain actions)
    """

    def has_permission(self, request, view):
        # Check system role-based permission first
        if hasattr(
            request.user, "has_module_permission"
        ) and request.user.has_module_permission("orders", "update"):
            return True

        # Fallback to legacy permission
        if self.has_staff_permission(request, "process_orders"):
            return True

        # Need object-level permission check for customers and sellers
        return True

    def has_object_permission(self, request, view, obj):
        # If they have general permission, they can access
        if hasattr(
            request.user, "has_module_permission"
        ) and request.user.has_module_permission("orders", "update"):
            return True

        if self.has_staff_permission(request, "process_orders"):
            return True

        # Sellers can process payments for their own orders
        if self.is_seller_order(request, obj):
            return True

        # Customers can only check payment status and initiate payment for their own orders
        if self.is_customer_order(request, obj):
            if view.action in ["check_payment_status", "initiate_payment"]:
                return True
            return False

        return False




# Add this to your permissions.py file

class CanRequestInvoice(BaseOrderPermission):
    """
    Permission for requesting invoice
    - Customers can request invoices for their own orders
    """

    def has_permission(self, request, view):
        # Need object-level permission check
        return True

    def has_object_permission(self, request, view, obj):
        # Only customers can request invoice for their own orders
        if hasattr(request.user, "customer") and request.user.customer:
            return self.is_customer_order(request, obj)
        return False