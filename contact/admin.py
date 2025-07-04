# contact/admin.py
from django.contrib import admin
from .models import ContactSubmission

@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    # List view configuration
    list_display = ['id', 'name', 'email', 'phone', 'subject', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'phone', 'subject', 'message']
    list_display_links = ['id', 'name']  # Make ID and name clickable
    ordering = ['-created_at']
    
    # Detail view configuration
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'customer'),
            'description': 'Basic contact details of the person who submitted this form.'
        }),
        ('Message Details', {
            'fields': ('subject', 'message'),
            'description': 'The subject and full message content.'
        }),
        ('Status & Metadata', {
            'fields': ('status', 'created_at'),
            'description': 'Submission status and timestamps.'
        }),
    )
    
    # Optional: Add custom actions
    actions = ['mark_as_responded', 'mark_as_closed']
    
    def mark_as_responded(self, request, queryset):
        updated = queryset.update(status='responded')
        self.message_user(request, f'{updated} submissions marked as responded.')
    mark_as_responded.short_description = 'Mark selected as responded'
    
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f'{updated} submissions marked as closed.')
    mark_as_closed.short_description = 'Mark selected as closed'
    
    # Optional: Customize how the customer field is displayed
    def get_readonly_fields(self, request, obj=None):
        """Make all fields readonly when viewing an existing submission"""
        if obj:  # Editing an existing object
            return self.readonly_fields + ['name', 'email', 'phone', 'subject', 'message', 'customer']
        return self.readonly_fields
    
    # Optional: Add color coding to status in list view
    def get_list_display(self, request):
        """Customize list display"""
        return self.list_display
    
    # Change form layout for better readability
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'message' in form.base_fields:
            form.base_fields['message'].widget.attrs['rows'] = 10
            form.base_fields['message'].widget.attrs['cols'] = 80
        return form