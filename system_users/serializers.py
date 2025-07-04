from rest_framework import serializers
from django.contrib.auth import get_user_model
from system_users.models import Role, SystemModule, ModulePermission, QRCode, PasswordResetToken

User = get_user_model()

### ✅ User and Seller Login Serializer ###
class LoginSerializer(serializers.Serializer):
    """Basic login serializer for email and password"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class SellerLoginSerializer(serializers.Serializer):
    """Two-step login serializer for sellers"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    otp = serializers.CharField(required=False)  # Optional for first step

### ✅ User Creation Serializer ###
class UserCreateSerializer(serializers.Serializer):
    """Serializer for creating a new system user"""
    email = serializers.EmailField()
    name = serializers.CharField(max_length=255)
    role = serializers.CharField(max_length=100)

    def validate_role(self, value):
        """Ensure the role exists"""
        if not Role.objects.filter(name=value).exists():
            raise serializers.ValidationError("Role does not exist")
        return value

### ✅ Role & Permission Serializers ###
class SystemModuleSerializer(serializers.ModelSerializer):
    """Serializer for System Modules"""
    class Meta:
        model = SystemModule
        fields = ["id", "name", "description"]

class ModulePermissionSerializer(serializers.ModelSerializer):
    """Serializer for Module Permissions"""
    module = SystemModuleSerializer(read_only=True)

    class Meta:
        model = ModulePermission
        fields = ["id", "module", "permissions"]

class RoleDetailSerializer(serializers.ModelSerializer):
    """Detailed Role serializer with permissions"""
    module_permissions = ModulePermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ["id", "name", "description", "is_active", "module_permissions"]

### ✅ User Detail Serializer ###
class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for retrieving user details"""
    role = RoleDetailSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source="role", write_only=True, required=False
    )

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "role_id", "is_active", "is_staff", "is_admin", "created_at", "updated_at"]

### ✅ User Profile Update Serializer ###
class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    class Meta:
        model = User
        fields = ["name", "address", "phone_number", "profile_image"]

### ✅ QR Code Serializer ###
class QRCodeSerializer(serializers.ModelSerializer):
    """Serializer for QR Code Generation"""
    class Meta:
        model = QRCode
        fields = ["qr_code_url", "expires_at"]

### ✅ OTP Verification Serializer ###
class OTPVerifySerializer(serializers.Serializer):
    """Serializer for verifying OTP"""
    otp = serializers.CharField(max_length=6, required=True)

### ✅ Password Reset Serializers ###
class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset using a token"""
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing user password"""
    old_password = serializers.CharField(write_only=True, min_length=8)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        """Ensure the old password is correct"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value


# for role based permisssions
# system_users/serializers.py
# Add these serializers to your existing serializers.py file


class SystemModuleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating System Modules"""

    class Meta:
        model = SystemModule
        fields = ["name", "description"]


class ModulePermissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Module Permissions"""

    module_name = serializers.CharField(write_only=True)

    class Meta:
        model = ModulePermission
        fields = ["module_name", "permissions"]

    def validate_module_name(self, value):
        """Ensure the module exists"""
        if not SystemModule.objects.filter(name=value).exists():
            raise serializers.ValidationError("Module does not exist")
        return value

    def create(self, validated_data):
        module_name = validated_data.pop("module_name")
        module = SystemModule.objects.get(name=module_name)
        return ModulePermission.objects.create(module=module, **validated_data)


class RoleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Roles"""

    class Meta:
        model = Role
        fields = ["name", "description", "is_active"]


class RolePermissionAssignSerializer(serializers.Serializer):
    """Serializer for assigning permissions to a role"""

    module_name = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())

    def validate_module_name(self, value):
        """Ensure the module exists"""
        if not SystemModule.objects.filter(name=value).exists():
            raise serializers.ValidationError("Module does not exist")
        return value


class RoleUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Role basic information"""

    class Meta:
        model = Role
        fields = ["description", "is_active"]
