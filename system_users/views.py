# system_users/views.py
# Complete updated views including role management and appropriate permissions

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from system_users.serializers import (
    UserCreateSerializer,
    UserDetailSerializer,
    PasswordResetSerializer,
    PasswordChangeSerializer,
    QRCodeSerializer,
    UserProfileSerializer,
    SellerLoginSerializer,
    LoginSerializer,
    # New serializers for role management
    RoleDetailSerializer,
    SystemModuleSerializer,
    ModulePermissionSerializer,
    SystemModuleCreateSerializer,
    ModulePermissionCreateSerializer,
    RoleCreateSerializer,
    RolePermissionAssignSerializer,
    RoleUpdateSerializer,
)
from system_users.services import (
    create_system_user,
    generate_qr_code,
    verify_otp,
    generate_password_reset_token,
    send_password_reset_email,
    reset_user_password,
    update_user_profile,
)
from system_users.models import Role, SystemModule, ModulePermission
from system_users.permissions import (
    IsSuperAdmin,
    HasModulePermission,
    CanManageUsers,
    ReadOnly,
    CanManageRoles,
    CanViewModulePermissions,
    IsSystemUser,
)

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """Regular user login endpoint"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=email, password=password)

        if user is not None:
            # Only print if user exists
            print(user.is_superuser)

            if not user.is_active:
                return Response(
                    {"error": "Account is disabled."}, status=status.HTTP_403_FORBIDDEN
                )

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserDetailSerializer(user).data,
                }
            )

        return Response(
            {"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


import base64
import binascii
import pyotp


@api_view(["POST"])
@permission_classes([AllowAny])
def seller_login(request):
    """
    Enhanced seller login with robust 2FA handling
    """
    serializer = SellerLoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    # Authenticate user
    user = authenticate(request, email=email, password=password)

    if not user:
        return Response(
            {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
        )

    # Check and validate 2FA
    if user.otp_secret:
        otp = serializer.validated_data.get("otp")

        # If OTP not provided during first step
        if not otp:
            try:
                # Validate existing OTP secret
                base64.b32decode(user.otp_secret, casefold=True)

                # Generate QR Code for 2FA
                qr_data = generate_qr_code(user)
                return Response(
                    {
                        "message": "Please provide OTP to complete login",
                        "require_otp": True,
                        "qr_data": qr_data,
                    }
                )
            except (binascii.Error, TypeError):
                # Invalid secret, regenerate
                user.otp_secret = pyotp.random_base32()
                user.save()

                qr_data = generate_qr_code(user)
                return Response(
                    {
                        "message": "2FA secret reset. Please reconfigure.",
                        "require_otp": True,
                        "qr_data": qr_data,
                    }
                )

        # Verify OTP
        success, message = verify_otp(user, otp)
        if not success:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)

    # Generate tokens
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserDetailSerializer(user).data,
        }
    )


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing system users"""

    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated, CanManageUsers]
    basename = "system_users"  # Important for HasModulePermission checks

    @action(detail=False, methods=["post"])
    def create_user(self, request):
        """Allow Super Admins to create a new system user"""
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            name = serializer.validated_data["name"]
            role_name = serializer.validated_data["role"]

            try:
                user, created = create_system_user(email, name, role_name)
                if created:
                    return Response(
                        {"message": "User created successfully & email sent."},
                        status=status.HTTP_201_CREATED,
                    )
                return Response(
                    {"message": "User already exists."}, status=status.HTTP_200_OK
                )
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def assign_role(self, request, pk=None):
        """Allow admins to assign a role to a user"""
        user = self.get_object()
        role_id = request.data.get("role_id")

        role = get_object_or_404(Role, id=role_id)
        user.role = role
        user.save()
        return Response({"message": "Role assigned successfully."})

    @action(detail=False, methods=["put", "patch"])
    def update_profile(self, request):
        """Allow users to update their profile"""
        # This requires only authentication, as users can update their own profiles
        user = request.user
        serializer = UserProfileSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get the current user's details"""
        # Only requires authentication
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)


class SystemModuleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing system modules"""

    queryset = SystemModule.objects.all()
    serializer_class = SystemModuleSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    basename = "system_modules"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SystemModuleCreateSerializer
        return SystemModuleSerializer


class ModulePermissionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing module permissions"""

    queryset = ModulePermission.objects.all()
    serializer_class = ModulePermissionSerializer
    basename = "module_permissions"

    def get_permissions(self):
        """
        Different permissions for different actions:
        - List/Retrieve: Staff users can view
        - Create/Update/Delete: Only superadmins can modify
        """
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticated, CanViewModulePermissions]
        else:
            permission_classes = [IsAuthenticated, IsSuperAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ModulePermissionCreateSerializer
        return ModulePermissionSerializer


class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing roles"""

    queryset = Role.objects.all()
    serializer_class = RoleDetailSerializer
    permission_classes = [IsAuthenticated, CanManageRoles]
    basename = "roles"

    def get_serializer_class(self):
        if self.action == "create":
            return RoleCreateSerializer
        if self.action in ["update", "partial_update"]:
            return RoleUpdateSerializer
        return RoleDetailSerializer

    def get_permissions(self):
        """
        Different permissions for different actions:
        - List/Retrieve: Staff can view roles
        - Other actions: Only those with proper role management permissions
        """
        if self.action in ["list", "retrieve", "list_available_modules"]:
            # Allow staff to view roles
            permission_classes = [IsAuthenticated, IsSystemUser]
        else:
            # Role management requires specific permissions
            permission_classes = [IsAuthenticated, CanManageRoles]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=["post"])
    def assign_permissions(self, request, pk=None):
        """Assign specific module permissions to a role"""
        role = self.get_object()
        serializer = RolePermissionAssignSerializer(data=request.data)

        if serializer.is_valid():
            module_name = serializer.validated_data["module_name"]
            permissions = serializer.validated_data["permissions"]

            module = get_object_or_404(SystemModule, name=module_name)

            # Check if a permission with these exact settings already exists
            existing_perm = ModulePermission.objects.filter(
                module=module, permissions=permissions
            ).first()

            if existing_perm:
                module_perm = existing_perm
            else:
                # Create a new permission set for this role
                module_perm = ModulePermission.objects.create(
                    module=module, permissions=permissions
                )

            # Add this permission to the role
            role.module_permissions.add(module_perm)

            return Response(
                {
                    "message": f"Permissions for {module_name} assigned to {role.name}",
                    "permissions": permissions,
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def remove_module_permission(self, request, pk=None):
        """Remove a module's permissions from a role"""
        role = self.get_object()
        module_name = request.data.get("module_name")

        if not module_name:
            return Response(
                {"error": "Module name is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Find module permissions for this module
        module_perms = role.module_permissions.filter(module__name=module_name)
        if not module_perms.exists():
            return Response(
                {"error": f"No permissions found for {module_name}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Remove these permissions from the role
        for perm in module_perms:
            role.module_permissions.remove(perm)

        return Response(
            {"message": f"Permissions for {module_name} removed from {role.name}"}
        )

    @action(detail=False, methods=["get"])
    def list_available_modules(self, request):
        """List all available system modules"""
        modules = SystemModule.objects.all()
        serializer = SystemModuleSerializer(modules, many=True)
        return Response(serializer.data)


### ✅ 2FA (QR Code & OTP Verification) ###
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_qr(request):
    """Generate a QR Code for a user"""
    qr_data = generate_qr_code(request.user)
    serializer = QRCodeSerializer(data=qr_data)
    if serializer.is_valid():
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_otp_code(request):
    """Verify OTP Code"""
    otp = request.data.get("otp")
    success, message = verify_otp(request.user, otp)
    if success:
        return Response({"message": message}, status=status.HTTP_200_OK)
    return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)


### ✅ Password Reset Functionality ###
@api_view(["POST"])
@permission_classes([AllowAny])
def request_password_reset(request):
    """Generate password reset token and send email"""
    email = request.data.get("email")
    user = get_object_or_404(User, email=email)

    token = generate_password_reset_token(user)
    send_password_reset_email(user, token)

    return Response(
        {"message": "Password reset link sent to email."}, status=status.HTTP_200_OK
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset user password using token"""
    serializer = PasswordResetSerializer(data=request.data)
    if serializer.is_valid():
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        success, message = reset_user_password(token, new_password)
        if success:
            return Response({"message": message}, status=status.HTTP_200_OK)
        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Allow users to change their password"""
    serializer = PasswordChangeSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response(
            {"message": "Password changed successfully."}, status=status.HTTP_200_OK
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
