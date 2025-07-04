# system_users/permissions.py
import rest_framework.decorators
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.conf import settings

class IsSuperAdmin(BasePermission):
    """
    Allows access only to super admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

class IsSystemUser(BasePermission):
    """
    Allows access only to authenticated system users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class HasModulePermission(BasePermission):
    """
    Checks if the user has permission for the specific module and action.
    """

    def has_permission(self, request, view):
        # print(f"View: {view}")
        # print(f"View basename: {getattr(view, 'basename', 'N/A')}")
        # print(f"View action: {getattr(view, 'action', 'N/A')}")
        # Superusers have all permissions
        if request.user.is_superuser:
            return True

        # Get module name from view
        module = None
        if hasattr(view, "basename"):
            module = view.basename
            #print(module)
        elif hasattr(view, "get_module_name"):
            # Optional method to implement in views
            module = view.get_module_name()

        if not module:
            return False  # No module identified, deny access


        if module == "products" and request.user.role and request.user.role.name == "Seller":
            # Sellers have full access to their own products
            return True

        # Map HTTP methods to actions
        # Consider the viewset action if available
        if request.user.role:
            if hasattr(view, "action") and view.action:
            # Map custom actions to permissions
                action_permission_map = {
                "create_product": "create",
                "assign_role": "update",
                "update_profile": "update",
                "list":"read",
                "featured":"featured"
                # Add other custom actions as needed
                }
                action = action_permission_map.get(view.action, view.action)
              
            else:
            # Default to HTTP method mapping
                method_action_map = {
                "GET": "read",
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
                }
                action = method_action_map.get(request.method, "")

            # Check user's role permissions
            return request.user.has_module_permission(module, action)
        if request.method in ["GET"]:
            return True

        return False


class ReadOnly(BasePermission):
    """
    Allows read-only access.
    """
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

class CanManageUsers(BasePermission):
    """
    Permission class for user management.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        # Superusers can do everything
        if request.user.is_superuser:
            return True
            
        # Check specific module permissions
        if view.action in ['create', 'destroy']:
            return request.user.has_module_permission('system_users', 'create')
        elif view.action in ['update', 'partial_update']:
            return request.user.has_module_permission('system_users', 'update')
        elif view.action == 'list':
            return request.user.has_module_permission('system_users', 'read')
            
        return False

    def has_object_permission(self, request, view, obj):
        # Prevent users from modifying their own permissions
        if obj == request.user and view.action in ['destroy', 'deactivate']:
            return False
            
        # Superusers can do everything
        if request.user.is_superuser:
            return True
            
        # Users can view and update their own profile
        if view.action in ['retrieve', 'update', 'partial_update', 'me']:
            return obj == request.user
            
        return False

class CanManageRoles(BasePermission):
    """
    Permission class for role management.
    """
    def has_permission(self, request, view):
        # Only super admins can manage roles
        return request.user.is_superuser

class CanViewModulePermissions(BasePermission):
    """
    Permission class for viewing module permissions.
    """
    def has_permission(self, request, view):
        # Only staff users can view module permissions
        return request.user.is_staff and request.method in SAFE_METHODS
