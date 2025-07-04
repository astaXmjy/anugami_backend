# categories/admin.py
from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin
from django.utils.html import format_html
from .models import Category, CategoryImage, CategoryAttribute, CategorySEO

class CategoryImageInline(admin.TabularInline):
    model = CategoryImage
    extra = 1
    fields = ('image', 'alt_text', 'is_primary', 'sort_order')
    readonly_fields = ('width', 'height', 'file_size')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')

class CategoryAttributeInline(admin.TabularInline):
    model = CategoryAttribute
    extra = 1
    fields = ('name', 'type', 'is_required', 'is_filter', 'filter_type', 'options', 'sort_order')

class CategorySEOInline(admin.StackedInline):
    model = CategorySEO
    can_delete = False
    
    fieldsets = (
        ('Basic SEO', {
            'fields': ('page_title', 'meta_description', 'meta_keywords')
        }),
        ('Open Graph', {
            'fields': ('og_title', 'og_description', 'og_image'),
            'classes': ('collapse',)
        }),
        ('Advanced SEO', {
            'fields': ('canonical_url', 'robots_meta', 'schema_markup'),
            'classes': ('collapse',)
        })
    )

@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = (
        'tree_actions',
        'indented_title',
        'slug',
        'is_active',
        'is_featured',
        'product_count',
        'commission_rate',
        'gst_rate'
    )
    list_filter = ('is_active', 'is_featured', 'gst_rate', 'show_in_menu')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CategoryImageInline, CategoryAttributeInline, CategorySEOInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'parent')
        }),
        ('Display Settings', {
            'fields': (
                'is_active', 'is_featured', 'show_in_menu',
                'menu_order', 'display_order'
            )
        }),
        ('Financial Settings', {
            'fields': ('gst_rate', 'commission_rate'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('image', 'icon', 'banner'),
            'classes': ('collapse',)
        }),
        ('URL Settings', {
            'fields': ('custom_url', 'redirect_url'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    actions = ['make_active', 'make_inactive', 'make_featured', 'remove_featured']

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Activate selected categories"

    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = "Deactivate selected categories"

    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)
    make_featured.short_description = "Mark selected categories as featured"

    def remove_featured(self, request, queryset):
        queryset.update(is_featured=False)
    remove_featured.short_description = "Remove featured status"

    class Media:
        css = {
            'all': ('admin/css/category.css',)
        }
        js = ('admin/js/category.js',)

@admin.register(CategoryImage)
class CategoryImageAdmin(admin.ModelAdmin):
    list_display = ('category', 'image_preview', 'alt_text', 'is_primary', 'sort_order')
    list_filter = ('is_primary', 'category')
    search_fields = ('category__name', 'alt_text')
    ordering = ('category', 'sort_order')
    readonly_fields = ('width', 'height', 'file_size', 'image_preview')

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;"/>',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Preview'

@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = ('category', 'name', 'type', 'is_required', 'is_filter', 'filter_type')
    list_filter = ('is_filter', 'filter_type', 'type', 'is_required', 'category')
    search_fields = ('category__name', 'name')
    ordering = ('category', 'sort_order', 'name')