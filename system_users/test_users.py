from django.test import TestCase
from django.contrib.auth import get_user_model
from system_users.models import Role, SystemModule, ModulePermission, QRCode
from rest_framework.test import APIClient
from rest_framework import status
import pyotp

User = get_user_model()

class SystemUserTests(TestCase):
    """Test suite for system user functionalities"""

    def setUp(self):
        """Create test data"""
        self.client = APIClient()
        self.superadmin = User.objects.create_superuser(email="admin@example.com", password="AdminPass")
        self.user = User.objects.create_user(email="user@example.com", password="UserPass")
        
        # Create Roles & Permissions
        self.role = Role.objects.create(name="Manager", description="Can manage products")
        self.module = SystemModule.objects.create(name="products", description="Manage products")
        self.permission = ModulePermission.objects.create(module=self.module, permissions=["read", "create", "update", "delete"])
        self.role.module_permissions.add(self.permission)
        self.user.role = self.role
        self.user.save()

    def test_create_user(self):
        """Test Super Admin can create a new system user"""
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post("/users/create_user/", {"email": "newuser@example.com", "name": "New User", "role": "Manager"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_assign_role(self):
        """Test role assignment to a user"""
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post(f"/users/{self.user.id}/assign_role/", {"role_id": self.role.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_qr_code(self):
        """Test QR Code Generation for 2FA"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/generate-qr/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verify_otp(self):
        """Test OTP verification"""
        qr = QRCode.objects.create(user=self.user, secret=pyotp.random_base32())
        otp = pyotp.TOTP(qr.secret).now()

        self.client.force_authenticate(user=self.user)
        response = self.client.post("/verify-otp/", {"otp": otp})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_profile(self):
        """Test user profile update"""
        self.client.force_authenticate(user=self.user)
        response = self.client.put("/users/update_profile/", {"name": "Updated Name", "phone_number": "+123456789"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_request_password_reset(self):
        """Test password reset request"""
        response = self.client.post("/request-password-reset/", {"email": "user@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
