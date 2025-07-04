# customers/permissions.py
from rest_framework import permissions

class IsCustomerOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a customer profile to view or edit it.
    """
    def has_object_permission(self, request, view, obj):
        return obj.id == request.user.customer.id

class IsCustomerService(permissions.BasePermission):
    """
    Permission for customer service representatives.
    """
    def has_permission(self, request, view):
        return request.user.role and request.user.role.name == 'customer_service'

class IsSupportAgent(permissions.BasePermission):
    """
    Permission for support agents.
    """
    def has_permission(self, request, view):
        return request.user.role and request.user.role.name == 'support_agent'

    def has_object_permission(self, request, view, obj):
        # Support agents can only view, not modify
        if request.method in permissions.SAFE_METHODS:
            return True
        return False

class IsOrderManager(permissions.BasePermission):
    """
    Permission for order managers.
    """
    def has_permission(self, request, view):
        return request.user.role and request.user.role.name == 'order_manager'

class IsWarehouseManager(permissions.BasePermission):
    """
    Permission for warehouse managers.
    """
    def has_permission(self, request, view):
        return request.user.role and request.user.role.name == 'warehouse_manager'

class IsFinanceManager(permissions.BasePermission):
    """
    Permission for finance team.
    """
    def has_permission(self, request, view):
        if not request.user.role or request.user.role.name != 'finance_manager':
            return False
            
        # Specific endpoint permissions
        if view.action in ['wallet_transactions', 'refund_request']:
            return True
            
        return False

class IsMarketingManager(permissions.BasePermission):
    """
    Permission for marketing team.
    """
    def has_permission(self, request, view):
        if not request.user.role or request.user.role.name != 'marketing_manager':
            return False
            
        # Specific endpoint permissions
        if view.action in ['customer_segments', 'campaign_data']:
            return True
            
        return False

class AllowCustomerOwnerOrStaff(permissions.BasePermission):
    """
    Permission to allow customer owners or staff members to access.
    """
    def has_object_permission(self, request, view, obj):
        # Allow if user is staff
        if request.user.is_staff:
            return True
            
        # Allow if user is the customer
        return obj.id == request.user.customer.id

class CanManageCustomerData(permissions.BasePermission):
    """
    Permission for managing customer data (GDPR related).
    """
    def has_permission(self, request, view):
        if not request.user.role:
            return False
            
        allowed_roles = ['data_protection_officer', 'compliance_manager']
        return request.user.role.name in allowed_roles

class CanViewAnalytics(permissions.BasePermission):
    """
    Permission for viewing customer analytics.
    """
    def has_permission(self, request, view):
        if not request.user.role:
            return False
            
        analytics_roles = [
            'marketing_manager',
            'business_analyst',
            'product_manager'
        ]
        return request.user.role.name in analytics_roles

class CustomerPermissions:
    """
    Centralized permission mappings for different customer operations
    """
    @staticmethod
    def get_required_permissions(action):
        """
        Get required permissions for a specific action
        """
        permission_map = {
            # Profile operations
            'view_profile': [IsCustomerOwner | IsCustomerService | IsSupportAgent],
            'update_profile': [IsCustomerOwner | IsCustomerService],
            'delete_profile': [IsCustomerOwner | permissions.IsAdminUser],
            
            # Cart operations
            'cart_operations': [IsCustomerOwner],
            
            # Order operations
            'view_orders': [IsCustomerOwner | IsOrderManager | IsSupportAgent],
            'manage_orders': [IsOrderManager],
            
            # Financial operations
            'wallet_operations': [IsCustomerOwner | IsFinanceManager],
            'refund_operations': [IsFinanceManager],
            
            # Support operations
            'support_access': [IsCustomerService | IsSupportAgent],
            
            # Analytics operations
            'analytics_access': [CanViewAnalytics],
            
            # GDPR operations
            'gdpr_operations': [CanManageCustomerData],
            
            # Marketing operations
            'marketing_operations': [IsMarketingManager],
        }
        
        return permission_map.get(action, [permissions.IsAuthenticated])