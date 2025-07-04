from rest_framework import serializers
from .models import (
    SystemSetting, 
    EmailSetting, 
    ContactInfo, 
    Policy, 
    WebSetting, 
    FirebaseSetting, 
    PickupLocation,
    HeroSlide,
    BannerSection, 
    BannerItem
)

class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = "__all__"

class EmailSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSetting
        fields = "__all__"

class ContactInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInfo
        fields = "__all__"

class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = "__all__"

class WebSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebSetting
        fields = "__all__"

class FirebaseSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirebaseSetting
        fields = "__all__"

class PickupLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupLocation
        fields = "__all__"

class HeroSlideSerializer(serializers.ModelSerializer):
    """
    Serializer for the HeroSlide model
    """
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = HeroSlide
        fields = ['id', 'title', 'description', 'image', 'image_url', 'button_text', 
                 'button_link', 'category', 'display_order', 'is_active']
    
    def get_image_url(self, obj):
        """
        Get the full URL for the image
        """
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

class BannerItemSerializer(serializers.ModelSerializer):
    """Serializer for BannerItem model"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = BannerItem
        fields = [
            'id', 'title', 'subtitle', 'tagline', 'vertical_text', 'discount',
            'cta_text', 'cta_link', 'image', 'image_url', 'grid_column_span',
            'grid_row_span', 'display_order', 'text_position', 'is_explore_style',
            'text_color', 'custom_text_color', 'overlay_opacity'
        ]
    
    def get_image_url(self, obj):
        """Get the full URL for the image"""
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

class BannerSectionSerializer(serializers.ModelSerializer):
    """Serializer for BannerSection model"""
    banner_items = BannerItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = BannerSection
        fields = [
            'id', 'name', 'section_type', 'layout_preset', 'custom_css_class',
            'background_color', 'display_order', 'banner_items'
        ]

class BannerSectionPublicSerializer(serializers.ModelSerializer):
    """Serializer for public display of BannerSection"""
    items = serializers.SerializerMethodField()
    
    class Meta:
        model = BannerSection
        fields = [
            'id', 'name', 'section_type', 'layout_preset', 'custom_css_class',
            'background_color', 'items'
        ]
    
    def get_items(self, obj):
        """Get items sorted by display_order"""
        items = obj.banner_items.all().order_by('display_order')
        return BannerItemSerializer(items, many=True, context=self.context).data

class SimpleBannerItemSerializer(serializers.ModelSerializer):
    """Simplified serializer for banner items in frontend format"""
    imageSrc = serializers.SerializerMethodField()
    ctaText = serializers.CharField(source='cta_text', allow_null=True)
    ctaLink = serializers.CharField(source='cta_link', allow_null=True)
    isExploreStyle = serializers.BooleanField(source='is_explore_style')
    
    class Meta:
        model = BannerItem
        fields = [
            'id', 'imageSrc', 'title', 'subtitle', 'ctaText', 'ctaLink',
            'discount', 'tagline', 'verticalText', 'isExploreStyle',
            'grid_column_span', 'grid_row_span', 'text_position'
        ]
        extra_kwargs = {
            'title': {'source': 'title'},
            'subtitle': {'source': 'subtitle'},
            'discount': {'source': 'discount'},
            'tagline': {'source': 'tagline'},
            'verticalText': {'source': 'vertical_text'}
        }
    
    def get_imageSrc(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

class FrontendBannerSectionSerializer(serializers.ModelSerializer):
    """Serializer formatted specifically for easy frontend consumption"""
    banners = serializers.SerializerMethodField()
    sectionType = serializers.CharField(source='section_type')
    layoutPreset = serializers.CharField(source='layout_preset')
    customClass = serializers.CharField(source='custom_css_class', allow_null=True)
    backgroundColor = serializers.CharField(source='background_color', allow_null=True)
    
    class Meta:
        model = BannerSection
        fields = ['id', 'name', 'sectionType', 'layoutPreset', 'customClass', 'backgroundColor', 'banners']
    
    def get_banners(self, obj):
        items = obj.banner_items.all().order_by('display_order')
        return SimpleBannerItemSerializer(items, many=True, context=self.context).data    