from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role, SystemModule, ModulePermission, QRCode, PasswordResetToken

@admin.register(SystemModule)
class SystemModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")
    ordering = ("name",)

@admin.register(ModulePermission)
class ModulePermissionAdmin(admin.ModelAdmin):
    list_display = ("module", "permissions")
    search_fields = ("module__name", "permissions")
    ordering = ("module",)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "is_active")
    search_fields = ("name", "description")
    filter_horizontal = ("module_permissions",)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "name", "role", "is_active", "is_admin", "is_staff", "created_at")
    search_fields = ("email", "name")
    ordering = ("email",)
    list_filter = ("is_admin", "is_staff", "is_active")
    
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "address", "phone_number", "profile_image")}),
        ("Permissions", {"fields": ("role", "is_active", "is_admin", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "password1", "password2", "role"),
        }),
    )
    
    readonly_fields = ("created_at", "updated_at")

@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at")
    search_fields = ("user__email",)
    ordering = ("expires_at",)

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at")
    search_fields = ("user__email", "token")
    ordering = ("expires_at",)
