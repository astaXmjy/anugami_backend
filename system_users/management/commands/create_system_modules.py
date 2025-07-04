# system_users/management/commands/create_system_modules.py
from django.core.management.base import BaseCommand
from system_users.models import SystemModule

class Command(BaseCommand):
    help = 'Creates initial system modules'

    def handle(self, *args, **kwargs):
        modules = [
            {
                'name': 'blogs', 
                'description': 'Manage blog posts'
            },
            {
                'name': 'brands', 
                'description': 'Manage brand details'
            },
            {
                'name': 'categories', 
                'description': 'Manage product categories'
            },
            {
                'name': 'chat', 
                'description': 'Respond to customer chats'
            },
            {
                'name': 'customers', 
                'description': 'Manage customers'
            },
            {
                'name': 'faq', 
                'description': 'Manage FAQ entries'
            },
            {
                'name': 'featured_sections', 
                'description': 'Manage homepage featured sections'
            },
            {
                'name': 'locations', 
                'description': 'Manage locations'
            },
            {
                'name': 'logs', 
                'description': 'View system logs'
            },
            {
                'name': 'media', 
                'description': 'Manage media files'
            },
            {
                'name': 'media_management', 
                'description': 'Manage media storage and retrieval'
            },
            {
                'name': 'notifications', 
                'description': 'Send notifications to users'
            },
            {
                'name': 'offers', 
                'description': 'Manage promotional offers'
            },
            {
                'name': 'orders', 
                'description': 'Process customer orders'
            },
            {
                'name': 'payments', 
                'description': 'Process and manage payments'
            },
            {
                'name': 'permissions', 
                'description': 'Manage role-based access control'
            },
            {
                'name': 'products', 
                'description': 'Manage products in the catalog'
            },
            {
                'name': 'promo_codes', 
                'description': 'Manage discount promo codes'
            },
            {
                'name': 'reports', 
                'description': 'Generate system reports'
            },
            {
                'name': 'returns', 
                'description': 'Process return requests'
            },
            {
                'name': 'sellers', 
                'description': 'Approve and manage sellers'
            },
            {
                'name': 'sliders', 
                'description': 'Manage homepage sliders'
            },
            {
                'name': 'support_tickets', 
                'description': 'Respond to customer support tickets'
            },
            {
                'name': 'system_settings', 
                'description': 'Update system configurations'
            },
            {
                'name': 'system_users', 
                'description': 'Manage system users'
            }
        ]

        # Create or update modules
        for module_data in modules:
            SystemModule.objects.get_or_create(
                name=module_data['name'], 
                defaults={'description': module_data['description']}
            )

        self.stdout.write(self.style.SUCCESS('Successfully created system modules'))