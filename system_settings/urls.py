# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SystemSettingViewSet,
    EmailSettingViewSet,
    ContactInfoViewSet,
    PolicyViewSet,
    WebSettingViewSet,
    FirebaseSettingViewSet,
    PickupLocationViewSet,
    HeroSlideViewSet,
    BannerSectionViewSet,
    BannerItemViewSet,
)

# app_name='system_settings'

router = DefaultRouter()
router.register(r"system-settings", SystemSettingViewSet, basename="system_settings")
router.register(r"email-settings", EmailSettingViewSet, basename="email_settings")
router.register(r"contact-info", ContactInfoViewSet, basename="contact_info")
router.register(r"policies", PolicyViewSet, basename="policies")
router.register(r"web-settings", WebSettingViewSet, basename="web_settings")
router.register(
    r"firebase-settings", FirebaseSettingViewSet, basename="firebase_settings"
)
router.register(r"pickup-locations", PickupLocationViewSet, basename="pickup_locations")
router.register(r"hero-slides", HeroSlideViewSet, basename="hero_slides")

# Banner section routes
router.register(r"banner-sections", BannerSectionViewSet, basename="banner_sections")
router.register(r"banner-items", BannerItemViewSet, basename="banner_items")

# Direct URLs for actions
banner_items_urls = [
    path('banner-items/by-section/<int:section_id>/', BannerItemViewSet.as_view({'get': 'by_section'})),
    path('banner-items/update-order/', BannerItemViewSet.as_view({'post': 'update_order'})),
]

# Multi-banners routes (matched to frontend expected URLs)
multi_banners_urls = [
    path('multi-banners/sections/', BannerSectionViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('multi-banners/sections/<int:pk>/', BannerSectionViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    })),
    path('multi-banners/items/', BannerItemViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('multi-banners/items/<int:pk>/', BannerItemViewSet.as_view({
        'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
    })),
    path('multi-banners/items/by-section/<int:section_id>/', BannerItemViewSet.as_view({'get': 'by_section'})),
    path('multi-banners/items/update-order/', BannerItemViewSet.as_view({'post': 'update_order'})),
]

urlpatterns = [
    path("", include(router.urls)),
    *banner_items_urls,
    *multi_banners_urls,
]