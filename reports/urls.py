from django.urls import path
from .views import AnalyticsReportView

app_name = "report_analytics"

urlpatterns = [
    path("", AnalyticsReportView.as_view(), name="analytics-report"),
]
