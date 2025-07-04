# system_users/management/commands/create_superadmins.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from system_users.models import Role, SystemModule, ModulePermission

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates initial superadmin users for Anugami'

    def handle(self, *args, **kwargs):
        # Define superadmin details
        superadmins = [
            {
                'email': 'superadmin1@anugami.com',
                'password': 'Anugami@123',
                'name': 'Ankit Malawaliya',
                'first_name': 'Ankit',
                'last_name': 'Malawaliya'
            },
            {
                'email': 'superadmin2@anugami.com',
                'password': 'Anugami@123',
                'name': 'Soham Sharma',
                'first_name': 'Soham',
                'last_name': 'Sharma'
            },
            {
                'email': 'superadmin3@anugami.com',
                'password': 'Anugami@123',
                'name': 'Shubham Singh',
                'first_name': 'Shubham',
                'last_name': 'Singh'
            }
        ]

        # First, create the superadmin role if it doesn't exist
        superadmin_role, created = Role.objects.get_or_create(
            name='Super Admin',
            defaults={
                'description': 'Super Administrator with full system access'
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('Created Super Admin role'))

            # Create system module and permissions for superadmin
            system_module, _ = SystemModule.objects.get_or_create(
                name='system',
                defaults={'description': 'System-wide access'}
            )

            module_permission, _ = ModulePermission.objects.get_or_create(
                module=system_module,
                defaults={
                    'permissions': ['create', 'read', 'update', 'delete', 'admin']
                }
            )

            superadmin_role.module_permissions.add(module_permission)

        # Create superadmin users
        for admin_data in superadmins:
            try:
                user = User.objects.get(email=admin_data['email'])
                self.stdout.write(self.style.WARNING(
                    f"User {admin_data['email']} already exists"
                ))
            except User.DoesNotExist:
                user = User.objects.create_superuser(
                    email=admin_data['email'],
                    password=admin_data['password'],
                    name=admin_data['name']
                )
                # Set additional fields
                user.first_name = admin_data['first_name']
                user.last_name = admin_data['last_name']
                user.role = superadmin_role
                user.is_admin = True
                user.save()

                self.stdout.write(self.style.SUCCESS(
                    f"Successfully created superadmin user: {admin_data['email']}"
                ))

        self.stdout.write(self.style.SUCCESS('Superadmin setup completed'))