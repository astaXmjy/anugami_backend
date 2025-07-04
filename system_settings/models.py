from django.db import models
from django.utils.translation import gettext_lazy as _
import firebase_admin
from django.core.validators import MinValueValidator, MaxValueValidator

class SystemSetting(models.Model):
    """General system settings."""
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.key

class EmailSetting(models.Model):
    """Settings related to email configurations."""
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.IntegerField()
    smtp_username = models.CharField(max_length=255)
    smtp_password = models.CharField(max_length=255)
    use_ssl = models.BooleanField(default=True)

    def __str__(self):
        return f"Email Config: {self.smtp_host}"

class ContactInfo(models.Model):
    """Stores contact information for the company."""
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()

    def __str__(self):
        return self.email

class Policy(models.Model):
    """Stores various policies like privacy, return, shipping, admin, etc."""
    POLICY_TYPES = [
        ("privacy", "Privacy Policy"),
        ("return", "Return Policy"),
        ("shipping", "Shipping Policy"),
        ("admin", "Admin Policies"),
        ("seller", "Seller Policies"),
    ]
    policy_type = models.CharField(max_length=50, choices=POLICY_TYPES)
    content = models.TextField()

    def __str__(self):
        return self.policy_type


class WebSetting(models.Model):
    """General web settings like meta tags, branding, etc."""

    site_name = models.CharField(max_length=255)
    site_logo = models.ImageField(upload_to="logos/")
    meta_description = models.TextField()
    support_number = models.CharField(max_length=12)
    support_email = models.EmailField()
    copyright_details = models.TextField()
    address = models.CharField(max_length=244)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    zipcode = models.CharField(max_length=10)
    invoice_title = models.CharField(max_length=255)
    invoice_copyright_details = models.TextField()
    short_description = models.TextField()
    map_iframe = models.TextField()
    authorized_signatory = models.CharField(max_length=255)
    footer_logo = models.ImageField(upload_to="footers/")
    favicon = models.ImageField(upload_to="favicons/")
    meta_keywords = models.TextField()
    social_media_links_facebook = models.URLField()
    social_media_links_twitter = models.URLField()
    social_media_links_instagram = models.URLField()
    social_media_links_youtube = models.URLField()
    social_media_links_pinterest = models.URLField()
    social_media_links_linkedin = models.URLField()

    primary_color = models.CharField(max_length=7, default="#d03fc0")
    secondary_color = models.CharField(max_length=7, default="#ffbb4e")
    font_color = models.CharField(max_length=7, default="#000000")
    header_font_color = models.CharField(max_length=7, default="#ffffff")
    footer_font_color = models.CharField(max_length=7, default="#ffffff")
    header_font_hover_color = models.CharField(max_length=7, default="#ffbb4e")
    footer_font_hover_color = models.CharField(max_length=7, default="#d03fc0")
    header_background_color = models.TextField(
        default="background: rgb(0,0,0); background: -moz-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: -webkit-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%);"
    )
    footer_background_color = models.TextField(
        default="background: rgb(0,0,0); background: -moz-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: -webkit-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%);"
    )
    add_to_cart_hover_color = models.CharField(max_length=7, default="#ffffff")
    favorite_hover_color = models.CharField(max_length=7, default="#ffffff")
    add_to_cart_text_hover_color = models.CharField(max_length=7, default="#d03fc0")
    favorite_text_hover_color = models.CharField(max_length=7, default="#d03fc0")
    add_to_cart_text_color = models.CharField(max_length=7, default="#ffffff")
    favorite_text_color = models.CharField(max_length=7, default="#ffffff")
    add_to_cart_background_color = models.TextField(
        default="background: rgb(0,0,0); background: -moz-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: -webkit-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%);"
    )
    favorite_background_color = models.TextField(
        default="background: rgb(0,0,0); background: -moz-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: -webkit-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%);"
    )
    login_register_background_color = models.TextField(
        default="background: rgb(0,0,0); background: -moz-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: -webkit-linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%); background: linear-gradient(117deg, rgba(0,0,0,1) 31%, rgba(247,74,76,1) 72%);"
    )

    def __str__(self):
        return self.site_name


class FirebaseSetting(models.Model):
    """Firebase-related settings."""
    api_key = models.CharField(max_length=500)
    project_id = models.CharField(max_length=255)
    messaging_sender_id = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    auth_domain=models.CharField(max_length=255)
    database_url=models.CharField(max_length=255)
    storage_bucket=models.CharField(max_length=255)
    measurement_id=models.CharField(max_length=255)

    def __str__(self):
        return self.project_id

class PickupLocation(models.Model):
    """Defines pickup locations for orders."""
    location_name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.location_name

class shipRocket(models.Model):
    shipRocketEmail=models.EmailField()
    shipRocketPassword=models.CharField(max_length=255)

class phonePe(models.Model):
    phonePeApi=models.CharField(max_length=255)

class HeroSlide(models.Model):
    """
    Model to store hero section slides that can be managed by admins
    """
    title = models.CharField(max_length=100, verbose_name=_("Slide Title"))
    description = models.TextField(verbose_name=_("Slide Description"))
    image = models.ImageField(upload_to='hero_slides/', verbose_name=_("Slide Image"))
    button_text = models.CharField(max_length=50, verbose_name=_("Button Text"))
    button_link = models.CharField(max_length=255, verbose_name=_("Button Link"))
    category = models.CharField(max_length=50, default="FEATURED", verbose_name=_("Category Label"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    display_order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = _("Hero Slide")
        verbose_name_plural = _("Hero Slides")

    def __str__(self):
        return self.title
    

class BannerSection(models.Model):
    """Model to define banner sections on the website"""
    SECTION_TYPES = [
        ('grid', 'Grid Layout'),
        ('full_width', 'Full Width Banner'),
        ('staggered', 'Staggered Grid'),
        ('featured', 'Featured Products Banner')
    ]

    LAYOUT_PRESETS = [
        ('1_large_2_small', '1 Large + 2 Small'),
        ('3_equal', '3 Equal Size'),
        ('2_large_1_small', '2 Large + 1 Small'),
        ('1_full_width', 'Full Width Banner'),
        ('2_half_width', 'Two Half Width'),
        ('custom', 'Custom Layout')
    ]

    name = models.CharField(max_length=100, verbose_name=_("Section Name"))
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES, default='grid', verbose_name=_("Section Type"))
    layout_preset = models.CharField(max_length=20, choices=LAYOUT_PRESETS, default='3_equal', verbose_name=_("Layout Preset"))
    custom_css_class = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Custom CSS Class"))
    background_color = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Background Color"))
    display_order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'created_at']
        verbose_name = _("Banner Section")
        verbose_name_plural = _("Banner Sections")

    def __str__(self):
        return self.name

class BannerItem(models.Model):
    """Individual banner items within a section"""
    POSITION_CHOICES = [
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right'),
        ('top_left', 'Top Left'),
        ('top_right', 'Top Right'),
        ('bottom_left', 'Bottom Left'),
        ('bottom_right', 'Bottom Right'),
        ('custom', 'Custom Position')
    ]

    TEXT_COLOR_CHOICES = [
        ('light', 'Light (White)'),
        ('dark', 'Dark (Black)'),
        ('custom', 'Custom Color')
    ]

    section = models.ForeignKey(BannerSection, on_delete=models.CASCADE, related_name='banner_items')
    title = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Title"))
    subtitle = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Subtitle"))
    tagline = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Tagline"))
    vertical_text = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("Vertical Text"))
    discount = models.CharField(max_length=30, blank=True, null=True, verbose_name=_("Discount Text"))
    cta_text = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Button Text"))
    cta_link = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Button Link"))
    image = models.ImageField(upload_to='banners/', verbose_name=_("Banner Image"))
    
    # Layout settings
    grid_column_span = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(3)], verbose_name=_("Column Span"))
    grid_row_span = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(3)], verbose_name=_("Row Span"))
    display_order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))
    
    # Appearance settings
    text_position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='center', verbose_name=_("Text Position"))
    is_explore_style = models.BooleanField(default=False, verbose_name=_("Use Explore Style"))
    text_color = models.CharField(max_length=20, choices=TEXT_COLOR_CHOICES, default='light', verbose_name=_("Text Color"))
    custom_text_color = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Custom Text Color"))
    overlay_opacity = models.IntegerField(default=30, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name=_("Overlay Opacity (%)"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order']
        verbose_name = _("Banner Item")
        verbose_name_plural = _("Banner Items")

    def __str__(self):
        return f"{self.title or 'Banner'} - {self.section.name}"    