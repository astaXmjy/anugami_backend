from rest_framework.permissions import BasePermission

class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'customer')
            and request.user.customer is not None
        )

class IsSeller(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'seller_profile')
            and request.user.seller_profile is not None
        )

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin

class IsSupport(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff

class IsTicketOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_admin:
            return True
            
        if hasattr(request.user, 'customer') and request.user.customer:
            return obj.customer == request.user.customer
            
        if hasattr(request.user, 'seller_profile') and request.user.seller_profile:
            return obj.seller == request.user.seller_profile
            
        return False

class IsAssignedToTicket(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.assigned_to == request.user