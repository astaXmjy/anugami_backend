from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services import get_analytics
from .serializers import AnalyticsReportSerializer

class AnalyticsReportView(APIView):
    # permission_classes = [IsAuthenticated]  # Restrict access to authenticated users

    def get(self, request):
        analytics_data = get_analytics()
        serializer = AnalyticsReportSerializer(analytics_data)
        return Response(serializer.data)
