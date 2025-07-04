from django.contrib import admin
from django.utils.html import format_html
from django.db import models  # Added this import
from .models import FirestoreMedia, FirestoreProductImage

class FirestoreProductImageInline(admin.TabularInline):
    model = FirestoreProductImage
    extra = 1
    readonly_fields = ('position',)
    fields = ('product', 'is_primary', 'position')

@admin.register(FirestoreMedia)
class FirestoreMediaAdmin(admin.ModelAdmin):
    list_display = (
        'original_name',
        'content_type',
        'size_display',
        'directory',
        'user',
        'created_at',
        'preview_link'
    )
    list_filter = ('content_type', 'directory', 'created_at')
    search_fields = ('original_name', 'firestore_id', 'storage_path')
    readonly_fields = (
        'firestore_id',
        'original_name',
        'storage_path',
        'content_type',
        'size',
        'directory',
        'user',
        'created_at',
        'updated_at',
        'thumbnail_path',
        'preview_link'
    )
    inlines = [FirestoreProductImageInline]
    
    def size_display(self, obj):
        """Convert size to human readable format"""
        return obj.file_size_display
    size_display.short_description = 'Size'
    
    def preview_link(self, obj):
        """Generate preview link for images"""
        if obj.content_type.startswith('image/'):
            if obj.thumbnail_path:
                path = obj.thumbnail_path
            else:
                path = obj.storage_path
                
            return format_html(
                '<a href="{}" target="_blank">View Image</a>',
                f"https://storage.googleapis.com/{path}"
            )
        return "No preview available"
    preview_link.short_description = 'Preview'
    
    def has_add_permission(self, request):
        # Disable adding through admin as it's handled through the API
        return False
    
    def has_change_permission(self, request, obj=None):
        # Files are immutable once uploaded
        return False

@admin.register(FirestoreProductImage)
class FirestoreProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'media', 'is_primary', 'position')
    list_filter = ('is_primary', 'product')
    search_fields = ('product__name', 'media__original_name')
    raw_id_fields = ('product', 'media')
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return ('position',)
        return ()

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            # Set position to the next available position for this product
            max_position = FirestoreProductImage.objects.filter(
                product=obj.product
            ).aggregate(models.Max('position'))['position__max']
            obj.position = (max_position or 0) + 1
        super().save_model(request, obj, form, change)