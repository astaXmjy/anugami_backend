from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PromoCodeViewSet

app_name = "promo_codes"

router = DefaultRouter()
router.register(r"promocodes", PromoCodeViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
