from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OfferViewSet

app_name = 'offers'

router = DefaultRouter()
router.register(r"offers", OfferViewSet)

urlpatterns = [
    path("", include(router.urls)),  # Default CRUD endpoints
]
