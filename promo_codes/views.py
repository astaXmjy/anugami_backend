from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import PromoCode
from .serializers import PromoCodeSerializer, ApplyPromoCodeSerializer
from django.utils.timezone import now


class PromoCodeViewSet(viewsets.ModelViewSet):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer

    @action(detail=False, methods=["POST"])
    def apply(self, request):
        """
        API to validate and apply a promo code.
        Example request:
        {
            "promo_code": "SAVE20",
            "order_amount": 200
        }
        """
        serializer = ApplyPromoCodeSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.apply_promo_code()
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["GET"])
    def active(self, request):
        """
        Get all active promo codes.
        """
        active_promos = PromoCode.objects.filter(
            status="active", start_date__lte=now(), end_date__gte=now()
        )
        serializer = self.get_serializer(active_promos, many=True)
        return Response(serializer.data)
