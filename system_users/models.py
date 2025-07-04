from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import pyotp
import uuid
import os
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.core.validators import RegexValidator

### ✅ Custom User Manager ###
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_admin", True)  # Ensure superusers are also admins
        return self.create_user(email, password, **extra_fields)

### ✅ System Modules ###
class SystemModule(models.Model):
    """Defines all available modules in the system"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

### ✅ Module Permissions ###
class ModulePermission(models.Model):
    """Pre-defined system modules and their permissions"""
    module = models.ForeignKey(SystemModule, on_delete=models.CASCADE, related_name="permissions")
    permissions = models.JSONField(default=list)  # Store allowed actions in JSON format

    def __str__(self):
        return f"{self.module.name} - {self.permissions}"

### ✅ Role Model ###
class Role(models.Model):
    """User roles with module-wise permissions"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    module_permissions = models.ManyToManyField(ModulePermission, blank=True)
    is_active = models.BooleanField(default=True)

    def has_permission(self, module, action):
        """Check if role has specific permission"""
        try:
            module_perm = self.module_permissions.filter(module__name=module).first()
            return action in module_perm.permissions if module_perm else False
        except ModulePermission.DoesNotExist:
            return False

    def __str__(self):
        return self.name

### ✅ User Model ###
class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Main user model for authentication"""
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    address = models.TextField(null=True, blank=True)
    phone_number = models.CharField(
        max_length=15, 
        null=True, 
        blank=True, 
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', "Enter a valid phone number.")]
    )
    profile_image = models.ImageField(upload_to="profile_pics/", null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    is_admin = models.BooleanField(default=False)  # Track if a user is an admin
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    otp_secret = models.CharField(max_length=32, null=True, blank=True)  # 2FA Secret Key
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def generate_otp_secret(self):
        """Generate a new OTP secret"""
        self.otp_secret = pyotp.random_base32()
        self.save()

    def has_module_permission(self, module, action):
        """Check if user has permission for specific module action"""
        if self.is_superuser or self.is_admin:
            return True
        if not self.role:
            return False
        return self.role.has_permission(module, action)

    def __str__(self):
        return self.email

### ✅ Password Reset Token Model ###
class PasswordResetToken(models.Model):
    """Stores password reset tokens for users"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    # Should be changed to:
    def get_default_expiry():
        return now() + timedelta(hours=1)
    expires_at = models.DateTimeField(default=get_default_expiry)

    

    def is_expired(self):
        """Check if the token has expired"""
        return now() > self.expires_at

    def __str__(self):
        return f"Reset Token for {self.user.email}"

### ✅ User Activity Log ###
class UserActivityLog(models.Model):
    """Logs user actions"""
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email if self.user else 'Unknown'} - {self.action}"

### ✅ QR Code Model for 2FA ###
class QRCode(models.Model):
    """Stores generated QR codes for 2FA"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="qr_code")
    created_at = models.DateTimeField(auto_now_add=True)
    # Should be changed to:
    def get_default_expiry():
        return now() + timedelta(hours=1)
    expires_at = models.DateTimeField(default=get_default_expiry)

    secret = models.CharField(max_length=32, default=pyotp.random_base32())

    def generate_qr_code(self):
        """Generate a QR Code for Google Authenticator"""
        otp_uri = pyotp.totp.TOTP(self.secret).provisioning_uri(name=self.user.email, issuer_name="Anugami")
        qr_code_path = f"qrcodes/{self.user.email}.png"
        if not os.path.exists("qrcodes"):
            os.makedirs("qrcodes")
        import qrcode
        qr = qrcode.make(otp_uri)
        qr.save(qr_code_path)
        return qr_code_path

    def is_expired(self):
        """Check if the QR Code has expired"""
        return now() > self.expires_at

    def __str__(self):
        return f"QR Code for {self.user.email}"
