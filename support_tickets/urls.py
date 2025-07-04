from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SupportTicketViewSet, 
    TicketResponseViewSet,
    CreateSupportTicketView,
    TicketCategoryViewSet
)

router = DefaultRouter()
router.register(r"tickets", SupportTicketViewSet, basename="ticket")
router.register(r"responses", TicketResponseViewSet, basename="response")
router.register(r"categories", TicketCategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
    path("create-ticket/", CreateSupportTicketView.as_view(), name="create-ticket"),
    # Additional custom endpoints are already handled by @action decorators
]