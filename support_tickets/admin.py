# support_tickets/admin.py

from django.contrib import admin
from .models import SupportTicket, TicketResponse, TicketCategory, TicketNote

class TicketResponseInline(admin.TabularInline):
    model = TicketResponse
    extra = 0
    readonly_fields = ['created_at']

class TicketNoteInline(admin.TabularInline):
    model = TicketNote
    extra = 0
    readonly_fields = ['created_at']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'requester_name', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'requester_type', 'created_at']
    search_fields = ['subject', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_activity']
    inlines = [TicketResponseInline, TicketNoteInline]
    
    def requester_name(self, obj):
        if obj.requester_type == 'customer' and obj.customer:
            return f"{obj.customer.full_name} (Customer)"
        elif obj.requester_type == 'seller' and obj.seller:
            return f"{obj.seller.full_name} (Seller)"
        return "Unknown"
    
    requester_name.short_description = "Requester"

@admin.register(TicketResponse)
class TicketResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'responder_name', 'responder_type', 'created_at']
    list_filter = ['responder_type', 'created_at']
    search_fields = ['message', 'ticket__subject']
    readonly_fields = ['created_at']
    
    def responder_name(self, obj):
        if obj.customer:
            return obj.customer.full_name
        elif obj.seller:
            return obj.seller.full_name
        elif obj.staff:
            return obj.staff.name
        return "Unknown"
    
    responder_name.short_description = "Responder"

@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']

@admin.register(TicketNote)
class TicketNoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['note', 'ticket__subject']
    readonly_fields = ['created_at']