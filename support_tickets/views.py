from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import models

from orders.models import Order
from .models import SupportTicket, TicketResponse, TicketCategory, TicketNote
from .serializers import (
    SupportTicketSerializer, 
    TicketResponseSerializer,
    TicketCategorySerializer,
    TicketNoteSerializer
)
from .permissions import (
    IsCustomer, 
    IsSeller, 
    IsAdmin,
    IsSupport,
    IsTicketOwner,
    IsAssignedToTicket
)

class TicketCategoryViewSet(viewsets.ModelViewSet):
    queryset = TicketCategory.objects.all()
    serializer_class = TicketCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [permissions.IsAuthenticated()]

class CreateSupportTicketView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = SupportTicketSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            ticket = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'category', 'requester_type']
    search_fields = ['subject', 'description', 'id']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        
        # Admin and support staff can see all tickets
        if user.is_admin or user.is_staff:
            return SupportTicket.objects.all()
            
        # Seller can see tickets they created or are assigned to them
        if hasattr(user, 'seller_profile') and user.seller_profile:
            return SupportTicket.objects.filter(
                models.Q(seller=user.seller_profile) | 
                models.Q(assigned_to=user)
            )
            
        # Customer can only see their own tickets
        if hasattr(user, 'customer') and user.customer:
            return SupportTicket.objects.filter(customer=user.customer)
            
        return SupportTicket.objects.none()

    def get_permissions(self):
        if self.action in ['destroy']:
            return [permissions.IsAuthenticated(), IsAdmin()]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsTicketOwner() | IsAdmin() | IsSupport()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["post"])
    def add_response(self, request, pk=None):
        ticket = self.get_object()
        serializer = TicketResponseSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            
            # Create response based on user type
            if hasattr(user, 'customer') and user.customer:
                response = serializer.save(
                    ticket=ticket,
                    customer=user.customer,
                    responder_type='customer'
                )
            elif hasattr(user, 'seller_profile') and user.seller_profile:
                response = serializer.save(
                    ticket=ticket,
                    seller=user.seller_profile,
                    responder_type='seller'
                )
            elif user.is_staff or user.is_admin:
                response = serializer.save(
                    ticket=ticket,
                    staff=user,
                    responder_type='admin' if user.is_admin else 'support'
                )
            else:
                return Response(
                    {"error": "User type not recognized"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Update the ticket's last_activity and status if needed
            ticket.last_activity = timezone.now()
            
            # If a staff member responds to an open ticket, change status to in_progress
            if response.responder_type in ['support', 'admin'] and ticket.status == 'open':
                ticket.status = 'in_progress'
                
            # If a customer/seller responds to a resolved ticket, reopen it
            if response.responder_type in ['customer', 'seller'] and ticket.status == 'resolved':
                ticket.status = 'in_progress'
                
            ticket.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def add_note(self, request, pk=None):
        """Add an internal note to the ticket (staff only)"""
        if not (request.user.is_staff or request.user.is_admin):
            return Response(
                {"error": "Only staff members can add notes"}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        ticket = self.get_object()
        serializer = TicketNoteSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(ticket=ticket, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def order_details(self, request, pk=None):
        ticket = self.get_object()
        if not ticket.order_id:
            return Response(
                {"error": "No order associated with this ticket"}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        try:
            order = Order.objects.get(order_number=ticket.order_id)
            # You should create a proper OrderSerializer 
            # This is just a placeholder for the order data
            order_data = {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "total_amount": str(order.total_amount),
                "created_at": order.created_at
            }
            return Response(order_data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["patch"])
    def assign(self, request, pk=None):
        """Assign a ticket to a staff member"""
        if not (request.user.is_staff or request.user.is_admin):
            return Response(
                {"error": "Only staff members can assign tickets"}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        ticket = self.get_object()
        
        # Get the user to assign to
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {"error": "user_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            from system_users.models import CustomUser
            user = CustomUser.objects.get(id=user_id)
            
            # Make sure user is staff or admin
            if not (user.is_staff or user.is_admin):
                return Response(
                    {"error": "Can only assign to staff members"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            ticket.assigned_to = user
            ticket.save()
            
            return Response(
                {"message": f"Ticket assigned to {user.name}"},
                status=status.HTTP_200_OK
            )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["patch"])
    def change_status(self, request, pk=None):
        """Change ticket status with validation"""
        ticket = self.get_object()
        
        # Get the new status
        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {"error": "status is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Validate the status
        if new_status not in [status for status, _ in SupportTicket.TICKET_STATUS_CHOICES]:
            return Response(
                {"error": "Invalid status"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Set restrictions on who can set certain statuses
        user = request.user
        
        # Only staff/admin can set to resolved
        if new_status == 'resolved' and not (user.is_staff or user.is_admin):
            return Response(
                {"error": "Only staff can mark tickets as resolved"}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Only ticket owner can close a resolved ticket
        if new_status == 'closed':
            if ticket.status != 'resolved':
                return Response(
                    {"error": "Ticket must be resolved before closing"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Check if user is the ticket owner
            is_owner = False
            if hasattr(user, 'customer') and ticket.customer == user.customer:
                is_owner = True
            elif hasattr(user, 'seller_profile') and ticket.seller == user.seller_profile:
                is_owner = True
                
            if not (is_owner or user.is_staff or user.is_admin):
                return Response(
                    {"error": "Only the ticket owner or staff can close a ticket"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Update the ticket status
        ticket.status = new_status
        ticket.save()
        
        return Response(
            {"message": f"Ticket status updated to {new_status}"},
            status=status.HTTP_200_OK
        )

class TicketResponseViewSet(viewsets.ModelViewSet):
    serializer_class = TicketResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Admin and support staff can see all responses
        if user.is_admin or user.is_staff:
            return TicketResponse.objects.all()
            
        # Filter responses based on user type
        if hasattr(user, 'customer') and user.customer:
            # Customers can see responses to their tickets
            return TicketResponse.objects.filter(
                ticket__customer=user.customer
            )
            
        if hasattr(user, 'seller_profile') and user.seller_profile:
            # Sellers can see responses to their tickets or tickets assigned to them
            return TicketResponse.objects.filter(
                models.Q(ticket__seller=user.seller_profile) | 
                models.Q(ticket__assigned_to=user)
            )
            
        return TicketResponse.objects.none()
        
    def get_permissions(self):
        if self.action in ['destroy']:
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [permissions.IsAuthenticated()]