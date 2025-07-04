from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ReturnRequest
from .serializers import ReturnRequestSerializer

class ReturnViewSet(viewsets.ModelViewSet):
    """Handles product returns and refunds"""
    queryset = ReturnRequest.objects.all()
    serializer_class = ReturnRequestSerializer

    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        """Approve a return request"""
        return_request = self.get_object()
        return_request.status = "APPROVED"
        return_request.save()
        return Response({"message": "Return request approved"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        """Reject a return request"""
        return_request = self.get_object()
        return_request.status = "REJECTED"
        return_request.save()
        return Response({"message": "Return request rejected"}, status=status.HTTP_200_OK)
