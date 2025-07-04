from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from customers.models import Customer
from sellers.models import Seller
from orders.models import Order
from system_users.models import CustomUser

class TicketCategory(models.Model):
    """Categories for organizing support tickets"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class SupportTicket(models.Model):
    TICKET_STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    TICKET_PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    REQUESTER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('seller', 'Seller'),
        ('admin', 'Admin'),
    ]
    
    # Use Generic relation to support both Customer and Seller
    requester_type = models.CharField(max_length=20, choices=REQUESTER_TYPE_CHOICES, default='customer')
    
    # References to either Customer or Seller (only one should be filled)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='support_tickets', null=True, blank=True)
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='support_tickets', null=True, blank=True)
    
    # Related fields
    order_id = models.CharField(max_length=255, null=True, blank=True)
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    
    # Content fields
    subject = models.CharField(max_length=255)
    description = models.TextField()
    
    # Status fields
    status = models.CharField(max_length=20, choices=TICKET_STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=TICKET_PRIORITY_CHOICES, default='medium')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # Assignment
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    
    # SLA tracking
    sla_due_date = models.DateTimeField(null=True, blank=True)
    is_overdue = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Ticket #{self.id} - {self.subject}"
    
    def save(self, *args, **kwargs):
        # Make sure only one of customer or seller is set
        if self.customer and self.seller:
            raise ValueError("A ticket cannot be associated with both a customer and a seller")
        if not self.customer and not self.seller:
            raise ValueError("A ticket must be associated with either a customer or a seller")
            
        # Set the correct requester_type
        if self.customer:
            self.requester_type = 'customer'
        elif self.seller:
            self.requester_type = 'seller'
            
        super().save(*args, **kwargs)

class TicketResponse(models.Model):
    RESPONDER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('seller', 'Seller'),
        ('support', 'Support Team'),
        ('admin', 'Admin'),
    ]
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='responses')
    
    # Use Generic relation to support different user types
    responder_type = models.CharField(max_length=20, choices=RESPONDER_TYPE_CHOICES)
    
    # References to either Customer, Seller, or CustomUser (only one should be filled)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='ticket_responses', null=True, blank=True)
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='ticket_responses', null=True, blank=True)
    staff = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ticket_responses', null=True, blank=True)
    
    message = models.TextField()
    attachments = models.JSONField(null=True, blank=True)  # For storing file details
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Response to Ticket #{self.ticket.id}"
    
    def save(self, *args, **kwargs):
        # Make sure only one of customer, seller, or staff is set
        filled_fields = sum(1 for field in [self.customer, self.seller, self.staff] if field is not None)
        if filled_fields != 1:
            raise ValueError("A response must be associated with exactly one of: customer, seller, or staff")
            
        # Set the correct responder_type
        if self.customer:
            self.responder_type = 'customer'
        elif self.seller:
            self.responder_type = 'seller'
        elif self.staff:
            self.responder_type = 'support' if not self.staff.is_admin else 'admin'
            
        super().save(*args, **kwargs)

class TicketNote(models.Model):
    """Internal notes on tickets that are not visible to customers or sellers"""
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Note on Ticket #{self.ticket.id}"