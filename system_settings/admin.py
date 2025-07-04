from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SystemSetting,
    EmailSetting,
    ContactInfo,
    Policy,
    WebSetting,
    FirebaseSetting,
    PickupLocation,
    shipRocket,
    phonePe,
    HeroSlide,
    BannerSection, 
    BannerItem
)

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
    search_fields = ("key",)

@admin.register(EmailSetting)
class EmailSettingAdmin(admin.ModelAdmin):
    list_display = ("smtp_host", "smtp_port", "smtp_username", "use_ssl")
    search_fields = ("smtp_host", "smtp_username")

@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "email", "address")
    search_fields = ("email", "phone_number")

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("policy_type", "content")
    list_filter = ("policy_type",)
    search_fields = ("policy_type",)

@admin.register(WebSetting)
class WebSettingAdmin(admin.ModelAdmin):
    list_display = ("site_name", "support_number", "support_email")
    search_fields = ("site_name", "support_email")

@admin.register(FirebaseSetting)
class FirebaseSettingAdmin(admin.ModelAdmin):
    list_display = ("project_id", "api_key", "messaging_sender_id")
    search_fields = ("project_id", "api_key")

@admin.register(PickupLocation)
class PickupLocationAdmin(admin.ModelAdmin):
    list_display = ("location_name", "address", "latitude", "longitude")
    search_fields = ("location_name", "address")

@admin.register(shipRocket)
class ShipRocketAdmin(admin.ModelAdmin):
    list_display=('shipRocketEmail','shipRocketPassword')

@admin.register(phonePe)
class PhonePeAdmin(admin.ModelAdmin):
    list_display=('phonePeApi',)

@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'title', 'is_active', 'display_order', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description', 'button_text')
    list_editable = ('is_active', 'display_order')
    readonly_fields = ('preview_image',)
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'category')
        }),
        ('Image', {
            'fields': ('image', 'preview_image'),
        }),
        ('Button', {
            'fields': ('button_text', 'button_link'),
        }),
        ('Settings', {
            'fields': ('is_active', 'display_order'),
        }),
    )

    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="30" style="object-fit: cover;" />', obj.image.url)
        return "-"
    thumbnail.short_description = 'Image'

    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="300" style="max-height:200px; object-fit: contain;" />', obj.image.url)
        return "-"
    preview_image.short_description = 'Image Preview'


class BannerItemInline(admin.TabularInline):
    model = BannerItem
    extra = 0
    min_num = 1
    fields = ('image', 'thumbnail', 'title', 'subtitle', 'cta_text', 'cta_link', 'display_order', 'grid_column_span', 'grid_row_span')
    readonly_fields = ('thumbnail',)
    
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="60" style="object-fit: cover;" />', obj.image.url)
        return "-"
    thumbnail.short_description = 'Preview'

@admin.register(BannerSection)
class BannerSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'section_type', 'layout_preset', 'display_order', 'is_active', 'created_at', 'item_count')
    list_filter = ('section_type', 'layout_preset', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active', 'display_order')
    inlines = [BannerItemInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'section_type', 'layout_preset', 'is_active', 'display_order')
        }),
        ('Advanced Settings', {
            'fields': ('custom_css_class', 'background_color'),
            'classes': ('collapse',),
        }),
    )
    
    def item_count(self, obj):
        return obj.banner_items.count()
    item_count.short_description = 'Items'
    
    class Media:
        css = {
            'all': ('admin/css/banner_admin.css',)
        }
        js = ('admin/js/banner_admin.js',)

@admin.register(BannerItem)
class BannerItemAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'title', 'section', 'display_order')
    list_filter = ('section', 'text_position', 'is_explore_style')
    search_fields = ('title', 'subtitle', 'tagline')
    list_editable = ('display_order',)
    fieldsets = (
        (None, {
            'fields': ('section', 'image', 'preview')
        }),
        ('Content', {
            'fields': ('title', 'subtitle', 'tagline', 'vertical_text', 'discount'),
        }),
        ('Call to Action', {
            'fields': ('cta_text', 'cta_link', 'is_explore_style'),
        }),
        ('Layout', {
            'fields': ('display_order', 'grid_column_span', 'grid_row_span'),
        }),
        ('Appearance', {
            'fields': ('text_position', 'text_color', 'custom_text_color', 'overlay_opacity'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('preview',)
    
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80" height="50" style="object-fit: cover;" />', obj.image.url)
        return "-"
    thumbnail.short_description = 'Image'
    
    def preview(self, obj):
        if obj.image:
            return format_html(
                '<div style="position:relative; max-width:400px; border:1px solid #ddd; padding:10px;">'
                '<img src="{}" width="400" style="max-height:300px; object-fit:contain;" />'
                '<div style="position:absolute; top:0; left:0; right:0; bottom:0; display:flex; flex-direction:column; '
                'justify-content:{justify}; align-items:{align}; padding:20px; text-align:{text_align};">'
                '<div style="background-color:rgba(0,0,0,{overlay}); padding:10px; color:{color};">'
                '{tagline_html}'
                '{title_html}'
                '{subtitle_html}'
                '{discount_html}'
                '{button_html}'
                '</div>'
                '</div>'
                '</div>',
                obj.image.url,
                justify='center' if obj.text_position in ['center', 'left', 'right'] else 'flex-start' if 'top' in obj.text_position else 'flex-end',
                align='center' if obj.text_position in ['center', 'top', 'bottom'] else 'flex-start' if 'left' in obj.text_position else 'flex-end',
                text_align='center' if obj.text_position == 'center' else 'left' if 'left' in obj.text_position else 'right',
                overlay=obj.overlay_opacity / 100,
                color='#fff' if obj.text_color == 'light' else '#000' if obj.text_color == 'dark' else obj.custom_text_color or '#fff',
                tagline_html=f'<div style="font-size:12px; margin-bottom:5px;">{obj.tagline}</div>' if obj.tagline else '',
                title_html=f'<div style="font-size:24px; font-weight:bold; margin-bottom:5px;">{obj.title}</div>' if obj.title else '',
                subtitle_html=f'<div style="font-size:16px; margin-bottom:5px;">{obj.subtitle}</div>' if obj.subtitle else '',
                discount_html=f'<div style="font-size:18px; color:#ff6b6b; margin-bottom:10px;">{obj.discount}</div>' if obj.discount else '',
                button_html=f'<div style="display:inline-block; background-color:#fff; color:#000; padding:5px 15px; border-radius:3px;">{obj.cta_text}</div>' if obj.cta_text else ''
            )
        return "-"
    preview.short_description = 'Banner Preview'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Set the section queryset to only active sections
        if 'section' in form.base_fields:
            form.base_fields['section'].queryset = BannerSection.objects.filter(is_active=True)
        return form    