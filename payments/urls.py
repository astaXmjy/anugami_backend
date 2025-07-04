from django.urls import path
from .views import PaymentViewSet,PhonePeCallbackView

app_name = "payments"

urlpatterns = [
    path(
        "initiate_payment/",
        PaymentViewSet.as_view({"post": "initiate_payment"}),
        name="initiate_payment",
    ),
    path(
        "check_status/",
        PaymentViewSet.as_view({"get": "check_status"}),
        name="check_status",
    ),
    path(
        "refund_payment/",
        PaymentViewSet.as_view({"post": "refund_payment"}),
        name="refund_payment",
    ),
    path("phonepe-callback/", PhonePeCallbackView.as_view(), name="phonepe-callback"),
]
